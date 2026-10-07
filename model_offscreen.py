"""Dedicated offscreen GPU rendering: no native Qt child windows or UI-thread GL."""
import os
import math
import time
import threading
import queue
from types import SimpleNamespace
import numpy as np
from PyQt6.QtCore import QObject,pyqtSignal,Qt
from PyQt6.QtGui import QImage
from model_renderer import SoftwareModelRenderer

VERTEX='''#version 330
in vec3 position; in vec2 uv; in vec3 normal;
uniform mat3 rotation; uniform vec2 scale; uniform vec2 center; uniform float distance;
out vec2 texcoord; out vec3 n; out vec3 p;
void main(){p=rotation*position;float z=p.z+distance;
gl_Position=vec4(p.xy*scale+center*z,1.002002*z-0.2002002,z);
texcoord=vec2(uv.x,1.0-uv.y);n=rotation*normal;}
'''
FRAGMENT='''#version 330
uniform sampler2D base_map; uniform sampler2D normal_map; uniform sampler2D orm_map;
uniform bool textured; uniform bool mapped_normal; uniform bool mapped_orm;
uniform bool height_normal; uniform bool texture_alpha;
uniform vec3 diffuse; uniform float opacity; uniform float roughness; uniform float metallic;
in vec2 texcoord; in vec3 n; in vec3 p; out vec4 color;
void main(){vec4 base=textured?texture(base_map,texcoord)*vec4(diffuse,opacity):vec4(diffuse,opacity);
if(!texture_alpha) base.a=opacity;
if(base.a<0.03) discard;
vec3 N=normalize(n); if(!gl_FrontFacing) N=-N;
if(mapped_normal){vec3 dp1=dFdx(p),dp2=dFdy(p);vec2 du1=dFdx(texcoord),du2=dFdy(texcoord);
vec3 T=dp1*du2.y-dp2*du1.y;vec3 B=-dp1*du2.x+dp2*du1.x;
float norm=max(dot(T,T),dot(B,B));if(norm>0.000001){mat3 tbn=mat3(T*inversesqrt(norm),B*inversesqrt(norm),N);
vec3 detail=texture(normal_map,texcoord).xyz*2.0-1.0;
if(height_normal){float h=texture(normal_map,texcoord).r;detail=normalize(vec3(-dFdx(h)*3.0,-dFdy(h)*3.0,1.0));}
N=normalize(tbn*detail);}}
float r=roughness,m=metallic,ao=1.0;
if(mapped_orm){vec3 orm=texture(orm_map,texcoord).rgb;r*=orm.g;m*=orm.b;}
vec3 L=normalize(vec3(-0.4,0.7,-1.0));vec3 V=normalize(vec3(0.0,0.0,-6.0)-p);
float key=max(dot(N,L),0.0);float fill=max(dot(N,normalize(vec3(0.7,0.2,1.0))),0.0);
vec3 linear=pow(max(base.rgb,vec3(0)),vec3(2.2));
vec3 H=normalize(L+V);float spec=pow(max(dot(N,H),0.0),mix(100.0,8.0,clamp(r,0.05,1.0)));
vec3 lit=linear*(0.58+0.38*key+0.18*fill)+mix(vec3(0.035),linear,m)*spec*0.45;
color=vec4(pow(clamp(lit,0.0,1.0),vec3(1.0/2.2)),base.a);}
'''


class OffscreenRenderer:
    def __init__(self,scene):
        import moderngl
        self.gl=moderngl;self.ctx=moderngl.create_standalone_context(require=330)
        self.name='GPU / '+self.ctx.info.get('GL_RENDERER','OpenGL');self.is_gpu=True
        self.scene=scene;self.objects=[];self.targets=[];self.size=None;self.parts=[]
        try:
            self.program=self.ctx.program(vertex_shader=VERTEX,fragment_shader=FRAGMENT);self.objects.append(self.program)
            self.program['base_map']=0;self.program['normal_map']=1;self.program['orm_map']=2
            self.white=self.ctx.texture((1,1),4,bytes([255]*4));self.objects.append(self.white)
            texture_cache={}
            def upload(image):
                if image is None:return None
                key=image.cacheKey()
                if key in texture_cache:return texture_cache[key]
                maximum=min(8192,self.ctx.info['GL_MAX_TEXTURE_SIZE'])
                if max(image.width(),image.height())>maximum:image=image.scaled(maximum,maximum,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
                image=image.convertToFormat(QImage.Format.Format_RGBA8888)
                bits=image.constBits();bits.setsize(image.sizeInBytes())
                pixels=np.frombuffer(bits,dtype=np.uint8).reshape(image.height(),image.bytesPerLine())[:,:image.width()*4].copy()
                texture=self.ctx.texture((image.width(),image.height()),4,pixels.tobytes(),alignment=1)
                texture.build_mipmaps();texture.filter=(moderngl.LINEAR_MIPMAP_LINEAR,moderngl.LINEAR)
                texture.anisotropy=min(16,self.ctx.max_anisotropy);texture.repeat_x=True;texture.repeat_y=True
                self.objects.append(texture);texture_cache[key]=texture;return texture
            for (name,has_uv),data in scene.batches.items():
                faces=np.frombuffer(data,dtype=np.float32).reshape(-1,24)
                buffer=self.ctx.buffer(np.unique(faces,axis=0).tobytes());self.objects.append(buffer)
                vao=self.ctx.vertex_array(self.program,[(buffer,'3f 2f 3f','position','uv','normal')]);self.objects.append(vao)
                material=scene.materials[name]
                maps=[upload(material.get(key)) if has_uv else None for key in ('image','normal_image','orm_image')]
                self.parts.append((vao,material,maps))
        except Exception:
            self.close();raise

    def render(self,width,height,rotation,elevation,zoom,cancel=None,viewport=None,pan=(0,0),framing=1.0):
        started=time.perf_counter()
        if cancel and cancel.is_set():return None,0
        if self.size!=(width,height):
            for target in reversed(self.targets):target.release()
            self.targets=[];samples=min(4,self.ctx.max_samples)
            color=self.ctx.renderbuffer((width,height),components=4,samples=samples)
            depth=self.ctx.depth_renderbuffer((width,height),samples=samples)
            self.multisample=self.ctx.framebuffer([color],depth);self.resolved=self.ctx.simple_framebuffer((width,height),components=4)
            self.targets=[color,depth,self.multisample,self.resolved];self.size=(width,height)
        self.multisample.use();self.ctx.viewport=(0,0,width,height);self.multisample.clear(0,0,0,0,depth=1)
        self.ctx.enable_only(self.gl.DEPTH_TEST|self.gl.BLEND)
        self.ctx.blend_func=(self.gl.SRC_ALPHA,self.gl.ONE_MINUS_SRC_ALPHA,self.gl.ONE,self.gl.ONE_MINUS_SRC_ALPHA)
        c,s=math.cos(rotation),math.sin(rotation);ce,se=math.cos(elevation),math.sin(elevation)
        matrix=np.array([[c,0,s],[se*s,ce,-se*c],[-ce*s,se,ce*c]],dtype=np.float32)
        logical_width,logical_height=viewport or (width,height)
        scale=max(1,min(logical_width-40,logical_height-85))*2*zoom*framing
        self.program['rotation'].write(matrix.T.copy().tobytes());self.program['scale']=(2*scale/logical_width,2*scale/logical_height)
        self.program['center']=(2*pan[0]/logical_width,.02-2*pan[1]/logical_height)
        self.program['distance']=max(5.5,self.scene.radius*3.4)
        for vao,material,maps in self.parts:
            if cancel and cancel.is_set():return None,0
            for unit,texture in enumerate(maps):(texture or self.white).use(unit)
            self.program['textured']=maps[0] is not None;self.program['mapped_normal']=maps[1] is not None;self.program['mapped_orm']=maps[2] is not None
            self.program['height_normal']=material.get('normal_image') is not None and material['normal_image'].isGrayscale()
            self.program['diffuse']=material.get('color',(1,1,1));self.program['opacity']=material.get('opacity',1.0)
            self.program['texture_alpha']=material.get('texture_alpha',True)
            self.program['roughness']=material.get('roughness',.65);self.program['metallic']=material.get('metallic',0.0)
            vao.render(self.gl.TRIANGLES)
        self.ctx.copy_framebuffer(self.resolved,self.multisample)
        pixels=self.resolved.read(components=4,alignment=1)
        image=QImage(pixels,width,height,width*4,QImage.Format.Format_RGBA8888_Premultiplied).mirrored(False,True).copy()
        return image,(time.perf_counter()-started)*1000

    def close(self):
        for item in reversed(self.targets+self.objects):
            try:item.release()
            except Exception:pass
        self.targets=[];self.objects=[];self.ctx.release()


class RenderWorker(QObject):
    finished=pyqtSignal(object,object,str)
    done=pyqtSignal()
    def __init__(self,parent=None):
        super().__init__(parent);self.jobs=queue.Queue(maxsize=1);self.stopped=threading.Event()
        self.done.connect(self.deleteLater)
        self.thread=threading.Thread(target=self.work,name='Pylerium model renderer',daemon=True);self.thread.start()

    def submit(self,scene,key,options,cancel):
        try:self.jobs.get_nowait()
        except queue.Empty:pass
        self.jobs.put_nowait((scene,key,options,cancel))

    def stop(self):
        self.stopped.set()
        try:self.jobs.get_nowait()
        except queue.Empty:pass
        try:self.jobs.put_nowait(None)
        except queue.Full:pass

    def work(self):
        backend=None;current=None;gpu_failed=os.environ.get('PYLERIUM_RENDERER')=='software';reason=''
        try:
            while not self.stopped.is_set():
                job=self.jobs.get()
                if job is None:break
                scene,key,options,cancel=job
                if cancel.is_set():continue
                error='';result=None
                try:
                    if scene is not current:
                        if backend and hasattr(backend,'close'):backend.close()
                        backend=None
                        if not gpu_failed:
                            try:backend=OffscreenRenderer(scene)
                            except Exception as exc:gpu_failed=True;reason=str(exc)
                        if backend is None:backend=SoftwareModelRenderer(scene)
                        current=scene
                    try:image,elapsed=backend.render(cancel=cancel,**options)
                    except Exception as exc:
                        if not getattr(backend,'is_gpu',False):raise
                        backend.close();gpu_failed=True;reason=str(exc);backend=SoftwareModelRenderer(scene)
                        image,elapsed=backend.render(cancel=cancel,**options)
                    info=SimpleNamespace(is_gpu=getattr(backend,'is_gpu',False),name=getattr(backend,'name','Software'),reason=reason)
                    result=(info,image,elapsed)
                except Exception as exc:error=str(exc)
                if not self.stopped.is_set():
                    try:self.finished.emit(key,result,error)
                    except RuntimeError:break
        finally:
            if backend and hasattr(backend,'close'):backend.close()
            try:self.done.emit()
            except RuntimeError:pass
