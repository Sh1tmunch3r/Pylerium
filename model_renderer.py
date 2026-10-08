"""Complete, perspective-correct CPU surfaces, rendered off the GUI thread.

NumPy projects vertices and rasterizes bounded pixel packets in native loops.
No native child windows, per-face QPainter transforms or sparse mesh sampling.
"""
import math
import time

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage


class SoftwareModelRenderer:
    def __init__(self, scene):
        self.scene = scene
        self.parts = []
        for (name, has_uv), batch in scene.batches.items():
            vertices = np.frombuffer(batch, dtype=np.float32).reshape(-1, 3, 8)
            # Exporters sometimes duplicate complete faces. They contribute no
            # extra surface, but can multiply large-triangle overdraw thousands
            # of times. Remove exact duplicates once, retaining UVs and normals.
            vertices = np.unique(vertices.reshape(-1,24),axis=0).reshape(-1,3,8)
            material = scene.materials[name]
            image = material.get('image')
            pixels = None
            if image is not None and has_uv:
                if max(image.width(),image.height())>4096:
                    image = image.scaled(4096,4096,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
                image=image.convertToFormat(QImage.Format.Format_RGBA8888)
                bits = image.constBits(); bits.setsize(image.sizeInBytes())
                pixels = np.frombuffer(bits, dtype=np.uint8).reshape(image.height(), image.bytesPerLine())
                pixels = pixels[:, :image.width()*4].reshape(image.height(), image.width(), 4).copy()
            self.parts.append((vertices, material, pixels))

    def render(self, width, height, rotation, elevation, zoom, cancel=None, viewport=None,pan=(0,0),framing=1.0):
        started = time.perf_counter()
        rgba = np.zeros((height, width, 4), dtype=np.uint8)
        depth_buffer = np.full(width*height, np.inf, dtype=np.float32)
        frame = rgba.reshape(-1, 4)
        c, s = math.cos(rotation), math.sin(rotation)
        ce, se = math.cos(elevation), math.sin(elevation)
        # Same rotation, camera and framing as the floor/wireframe overlay.
        matrix = np.array([[c,0,s],[se*s,ce,-se*c],[-ce*s,se,ce*c]], dtype=np.float32)
        distance = max(5.5, self.scene.radius*3.4)
        logical_width,logical_height = viewport or (width,height)
        scale = max(1,min(logical_width-40,logical_height-85))*2.0*zoom*framing
        drawn = 0
        for vertices, material, texture in self.parts:
            if cancel is not None and cancel.is_set():
                return None, 0
            points = vertices[:,:,:3] @ matrix.T
            z = points[:,:,2] + distance
            inverse_z = 1 / np.maximum(z, 0.1)
            screen = points[:,:,:2] * inverse_z[:,:,None] * scale
            screen[:,:,0] *= width/logical_width
            screen[:,:,1] *= height/logical_height
            screen[:,:,0] += width/2+pan[0]*width/logical_width
            screen[:,:,1] = height*0.49 - screen[:,:,1]+pan[1]*height/logical_height
            lower = np.floor(screen.min(axis=1)).astype(np.int32)
            upper = np.ceil(screen.max(axis=1)).astype(np.int32)
            lower[:,0] = np.clip(lower[:,0],0,width-1); lower[:,1] = np.clip(lower[:,1],0,height-1)
            upper[:,0] = np.clip(upper[:,0],0,width-1); upper[:,1] = np.clip(upper[:,1],0,height-1)
            box_width = upper[:,0]-lower[:,0]+1
            box_height = upper[:,1]-lower[:,1]+1
            ax,ay = screen[:,0,0],screen[:,0,1]
            bx,by = screen[:,1,0],screen[:,1,1]
            cx,cy = screen[:,2,0],screen[:,2,1]
            denom = (by-cy)*(ax-cx)+(cx-bx)*(ay-cy)
            area = box_width*box_height
            valid = (np.abs(denom)>1e-5) & (z.min(axis=1)>0.1)
            normal = vertices[:,0,5:8] @ matrix.T
            light = 0.48 + 0.52*np.abs(normal @ np.array([0.2387,0.5569,0.7956], dtype=np.float32))
            # Small triangles travel together; large triangles cannot inflate the
            # working set of thousands of tiny triangles in the same packet.
            order = np.flatnonzero(valid)
            order = order[np.argsort(area[order])]
            cursor = 0
            while cursor < len(order):
                if cancel is not None and cancel.is_set():
                    return None, 0
                end = min(cursor+256,len(order))
                while end>cursor+1 and area[order[end-1]]*(end-cursor)>262144:
                    end = cursor + max(1,(end-cursor)//2)
                ids = order[cursor:end]; cursor = end
                count = area[ids]
                pixel = np.arange(int(count.max()),dtype=np.int32)[None,:]
                xs = lower[ids,0,None] + pixel % box_width[ids,None]
                ys = lower[ids,1,None] + pixel // box_width[ids,None]
                sx,sy = xs+0.5,ys+0.5
                w0 = ((by[ids,None]-cy[ids,None])*(sx-cx[ids,None])+
                      (cx[ids,None]-bx[ids,None])*(sy-cy[ids,None]))/denom[ids,None]
                w1 = ((cy[ids,None]-ay[ids,None])*(sx-cx[ids,None])+
                      (ax[ids,None]-cx[ids,None])*(sy-cy[ids,None]))/denom[ids,None]
                w2 = 1-w0-w1
                inside = (pixel<count[:,None]) & (w0>=-1e-6) & (w1>=-1e-6) & (w2>=-1e-6)
                face,pixel_index = np.nonzero(inside)
                if not len(face):
                    continue
                triangle = ids[face]
                weights = np.column_stack((w0[face,pixel_index],w1[face,pixel_index],w2[face,pixel_index]))
                perspective = weights * inverse_z[triangle]
                reciprocal = perspective.sum(axis=1)
                depths = 1/reciprocal
                positions = ys[face,pixel_index]*width+xs[face,pixel_index]
                nearer = depths <= depth_buffer[positions]
                triangle,positions,depths,perspective,reciprocal = (
                    values[nearer] for values in (triangle,positions,depths,perspective,reciprocal))
                if not len(positions):
                    continue
                if texture is not None:
                    uv = (vertices[triangle,:,3:5]*perspective[:,:,None]).sum(axis=1)/reciprocal[:,None]
                    # OBJ V points up. Repeat UVs rather than stretching outside
                    # the texture, and bilinearly sample the original aspect ratio.
                    tx = (uv[:,0]%1)*texture.shape[1]-0.5
                    ty = ((1-uv[:,1])%1)*texture.shape[0]-0.5
                    ix,iy = np.floor(tx).astype(np.int32),np.floor(ty).astype(np.int32)
                    fx,fy = (tx-ix)[:,None],(ty-iy)[:,None]
                    x0,x1 = ix%texture.shape[1],(ix+1)%texture.shape[1]
                    y0,y1 = iy%texture.shape[0],(iy+1)%texture.shape[0]
                    colors = ((texture[y0,x0]*(1-fx)+texture[y0,x1]*fx)*(1-fy)+
                              (texture[y1,x0]*(1-fx)+texture[y1,x1]*fx)*fy)
                else:
                    color = np.array([*material.get('color',(0.35,0.5,0.55)),1.0],dtype=np.float32)*255
                    colors = np.broadcast_to(color,(len(positions),4)).copy()
                colors[:,:3] *= light[triangle,None]
                if not material.get('texture_alpha',True):colors[:,3]=255
                colors[:,3] *= material.get('opacity',1.0)
                visible = colors[:,3] >= 8
                positions,depths,colors = positions[visible],depths[visible],colors[visible]
                # Resolve all overlapping samples in a packet, not just the last
                # face in OBJ order. Transparent texels do not occlude surfaces.
                np.minimum.at(depth_buffer,positions,depths)
                winners = depths <= depth_buffer[positions]+1e-5
                frame[positions[winners]] = np.clip(colors[winners],0,255).astype(np.uint8)
                drawn += len(ids)
        image = QImage(rgba.data,width,height,rgba.strides[0],QImage.Format.Format_RGBA8888).copy()
        return image,(time.perf_counter()-started)*1000
