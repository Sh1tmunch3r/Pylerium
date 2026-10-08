"""Worker-safe OBJ/MTL loading and portable dependency import."""
from __future__ import annotations
import math
import shlex
import shutil
import uuid
from array import array
from dataclasses import dataclass, field
from pathlib import Path

from PyQt6.QtCore import QSize,Qt
from PyQt6.QtGui import QImageReader

MODEL_FILTER = '3D models (*.obj *.glb *.gltf *.stl *.ply *.off)'
MODEL_FORMATS = {'.obj','.glb','.gltf','.stl','.ply','.off'}


def mesh_normals(mesh):
    """Preserve authored normals; otherwise generate angle-weighted normals without SciPy."""
    import numpy as np
    authored=mesh._cache.cache.get('vertex_normals')
    if authored is not None and np.shape(authored)==np.shape(mesh.vertices):return np.asarray(authored).copy()
    positions=np.asarray(mesh.vertices)[mesh.faces]
    face_normals=np.cross(positions[:,1]-positions[:,0],positions[:,2]-positions[:,0])
    face_normals/=np.maximum(np.linalg.norm(face_normals,axis=1)[:,None],1e-12)
    normals=np.zeros_like(mesh.vertices,dtype=float)
    for corner in range(3):
        first=positions[:,(corner+1)%3]-positions[:,corner]
        second=positions[:,(corner+2)%3]-positions[:,corner]
        divisor=np.linalg.norm(first,axis=1)*np.linalg.norm(second,axis=1)
        angle=np.arccos(np.clip(np.sum(first*second,axis=1)/np.maximum(divisor,1e-12),-1,1))
        np.add.at(normals,mesh.faces[:,corner],face_normals*angle[:,None])
    normals/=np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-12)
    return normals


def read_mesh_scene(path):
    """Local static geometry; glTF external dependencies must stay beside the model."""
    import json
    from urllib.parse import unquote
    import trimesh
    path=Path(path).resolve()
    if path.suffix.lower() not in MODEL_FORMATS:
        raise ValueError('Supported models: OBJ, GLB, glTF, STL, PLY and OFF')
    if path.stat().st_size>96_000_000:
        raise ValueError('Model exceeds 96 MB')
    if path.suffix.lower()=='.gltf':
        data=json.loads(path.read_text(encoding='utf-8'))
        total=path.stat().st_size
        for item in data.get('buffers',[])+data.get('images',[]):
            uri=item.get('uri','')
            if uri and not uri.startswith('data:'):
                resource=dependency(path.parent,unquote(uri),path.parent)
                total+=resource.stat().st_size
                if total>256_000_000: raise ValueError('Model bundle exceeds 256 MB')
    scene=trimesh.load_scene(str(path),process=False,allow_remote=False)
    if not scene.geometry: raise ValueError('Model contains no visible mesh geometry')
    count=sum(len(scene.geometry[scene.graph[node][1]].faces) for node in scene.graph.nodes_geometry)
    if count>300000: raise ValueError('Model exceeds 300k triangles')
    from PIL import Image
    for mesh in scene.geometry.values():
        if getattr(mesh.visual,'uv',None) is None:continue
        material=getattr(mesh.visual,'material',None)
        if material is None:continue
        existing=getattr(material,'baseColorTexture',None)
        if existing is None:existing=getattr(material,'image',None)
        if existing is not None:continue
        candidate=find_companion_texture(path,getattr(material,'name',''))
        if candidate:
            with Image.open(candidate) as image:
                picture=image.copy();picture.thumbnail((4096,4096))
            if hasattr(material,'baseColorTexture'):material.baseColorTexture=picture
            elif hasattr(material,'image'):material.image=picture
    return scene


def load_model(path,rotation=(0,0,0),root=None,texture=None,prefer_materials=True):
    """One preview representation for native OBJ and imported static mesh formats."""
    if Path(path).suffix.lower()=='.obj': return load_obj(path,rotation,root,texture,prefer_materials)
    import numpy as np
    from PyQt6.QtGui import QImage
    scene=read_mesh_scene(path)
    meshes=[]
    for node in scene.graph.nodes_geometry:
        transform,name=scene.graph[node]
        mesh=scene.geometry[name].copy(); mesh.apply_transform(transform)
        if len(mesh.faces): meshes.append(mesh)
    if not meshes: raise ValueError('Model contains no triangle surfaces')
    coords=np.concatenate([mesh.vertices for mesh in meshes])
    if len(coords)>500000 or not np.isfinite(coords).all(): raise ValueError('Invalid or oversized vertex geometry')
    low,high=coords.min(axis=0),coords.max(axis=0); span=(high-low).max()
    if span<=1e-12: raise ValueError('Model has no visible size')
    if len(rotation)!=3 or not all(math.isfinite(float(v)) for v in rotation): raise ValueError('Invalid rotation')
    materials={}; batches={}; vertices=[]; segments=[]; triangles=[]; warnings=[];picture_cache={}
    override=image_read(texture) if texture else None
    total_faces=sum(len(mesh.faces) for mesh in meshes)
    preview_step=max(1,math.ceil(total_faces/400));face_offset=0
    for ident,mesh in enumerate(meshes):
        points=(mesh.vertices-(low+high)/2)*3/span
        smooth_normals=mesh_normals(mesh)
        for axis,angle in enumerate(rotation):
            c,s=math.cos(math.radians(float(angle))),math.sin(math.radians(float(angle)))
            a,b=((1,2),(0,2),(0,1))[axis]
            first=points[:,a].copy(); second=points[:,b].copy()
            points[:,a]=first*c+second*s*(-1 if axis!=1 else 1)
            points[:,b]=first*s*(1 if axis!=1 else -1)+second*c
            first=smooth_normals[:,a].copy();second=smooth_normals[:,b].copy()
            smooth_normals[:,a]=first*c+second*s*(-1 if axis!=1 else 1)
            smooth_normals[:,b]=first*s*(1 if axis!=1 else -1)+second*c
        vertices.extend(map(tuple,points))
        visual=mesh.visual; mat=getattr(visual,'material',None)
        image=None if prefer_materials else override
        color=(1.0,1.0,1.0) if mat is not None else (.55,.6,.65)
        normal_image=orm_image=None;roughness=.65;metallic=0.0;opacity=1.0
        def picture_image(picture):
            if picture is None:return None
            cache_key=id(picture)
            if cache_key in picture_cache:return picture_cache[cache_key]
            picture=picture.copy();picture.thumbnail((4096,4096));picture=picture.convert('RGBA');raw=picture.tobytes()
            decoded=QImage(raw,picture.width,picture.height,picture.width*4,QImage.Format.Format_RGBA8888).copy()
            picture_cache[cache_key]=decoded;return decoded
        if mat is not None:
            diffuse=getattr(mat,'baseColorFactor',None)
            if diffuse is None: diffuse=getattr(mat,'diffuse',None)
            if diffuse is not None: color=tuple(float(v)/255 for v in diffuse[:3])
            if diffuse is not None and len(diffuse)>3:opacity=float(diffuse[3])/255
            picture=getattr(mat,'baseColorTexture',None)
            if picture is None: picture=getattr(mat,'image',None)
            if image is None and picture is not None:
                image=picture_image(picture)
            normal_image=picture_image(getattr(mat,'normalTexture',None))
            orm_image=picture_image(getattr(mat,'metallicRoughnessTexture',None))
            factor=getattr(mat,'roughnessFactor',None);roughness=.65 if factor is None else float(factor)
            metallic=float(getattr(mat,'metallicFactor',None) or 0)
        if image is None:image=override
        uv=getattr(visual,'uv',None); has_uv=uv is not None and len(uv)==len(points)
        if image is None and has_uv:
            candidate=find_companion_texture(path,getattr(mat,'name','') if mat is not None else '')
            if candidate:image=image_read(candidate,8192);color=(1,1,1)
        # Face/vertex colors become material groups, retaining PLY colour data.
        colors=visual.face_colors if getattr(visual,'kind',None)=='vertex' or getattr(visual,'kind',None)=='face' else None
        groups=[(None,np.arange(len(mesh.faces)))]
        if colors is not None:
            shades,inverse=np.unique(colors,axis=0,return_inverse=True)
            if len(shades)>512:
                colors=colors.copy();colors[:,:3]=(colors[:,:3]//64)*64+32
                if colors.shape[1]>3:colors[:,3]=255
                shades,inverse=np.unique(colors,axis=0,return_inverse=True)
                warnings.append('Large vertex-colour palette reduced to 64 preview colours')
            order=np.argsort(inverse,kind='stable');ends=np.cumsum(np.bincount(inverse))
            groups=list(zip(map(tuple,shades),np.split(order,ends[:-1])))
        for group,(shade,indices) in enumerate(groups):
            key=f'{ident}:{group}'
            materials[key]={'color':tuple(v/255 for v in shade[:3]) if shade else color,'image':image,
                            'name':getattr(mat,'name',None) or key,'automatic_texture':picture is not None if mat is not None else False,
                            'normal_image':normal_image,'orm_image':orm_image,'roughness':roughness,'metallic':metallic,
                            'opacity':float(shade[3])/255 if shade and len(shade)>3 else opacity}
            faces=mesh.faces[indices]; p=points[faces]
            normals=np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]); normals/=np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-12)
            data=np.zeros((len(faces),3,8),dtype=np.float32); data[:,:,:3]=p
            if has_uv: data[:,:,3:5]=np.asarray(uv)[faces]
            data[:,:,5:]=smooth_normals[faces]; batches[(key,has_uv)]=array('f',data.ravel())
            sample_indices=np.flatnonzero((indices+face_offset)%preview_step==0)
            for index in sample_indices:
                triangles.append((tuple(map(tuple,p[index])),tuple(map(tuple,data[index,:,3:5])),key,has_uv))
            for face in faces[sample_indices]:
                segments.extend((tuple(points[face[i]]),tuple(points[face[(i+1)%3]])) for i in range(3))
        face_offset+=len(mesh.faces)
    if Path(path).suffix.lower() in ('.glb','.gltf'): warnings.append('Static geometry; skeletal animation is not evaluated')
    if override is not None and prefer_materials and not any(mat.get('automatic_texture') for mat in materials.values()):
        warnings.append('No embedded diffuse images; using the assigned fallback texture. Matching diffuse maps are required for the original appearance.')
    if any(mat['image'] is not None for mat in materials.values()) and not any(key[1] for key in batches):
        warnings.append('Texture images found but no usable UVs; surfaces render with material colours')
    radius=max(math.sqrt(sum(v*v for v in point)) for point in vertices)
    return ModelScene(vertices,triangles,segments,materials,batches,warnings,radius,sum(len(m.faces) for m in meshes),triangles,segments)


@dataclass
class ModelScene:
    vertices: list
    triangles: list
    edges: list
    materials: dict
    batches: dict
    warnings: list = field(default_factory=list)
    radius: float = 1.5
    source_faces: int = 0
    preview_triangles: list = field(default_factory=list)
    preview_edges: list = field(default_factory=list)
    bounds: tuple = ()

    def __post_init__(self):
        if self.vertices and not self.bounds:
            low=[min(point[axis] for point in self.vertices) for axis in range(3)]
            high=[max(point[axis] for point in self.vertices) for axis in range(3)]
            self.bounds=tuple((x,y,z) for x in (low[0],high[0]) for y in (low[1],high[1]) for z in (low[2],high[2]))


def tokens(value):
    return shlex.split(value.replace('\\','/'), posix=True)


def dependency(base,value,root):
    value = value.replace('\\','/')
    path = (base/value).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f'Resource is outside the model folder: {value}')
    return path


def map_filename(value):
    """MTL map options precede the filename; unquoted spaces are retained."""
    parts = tokens(value)
    i = 0
    while i < len(parts) and parts[i].startswith('-'):
        option = parts[i]
        i += 1
        count = {'-mm':2,'-o':3,'-s':3,'-t':3}.get(option,1)
        if option in ('-o','-s','-t'):
            for _ in range(count):
                if i >= len(parts):
                    break
                try:
                    float(parts[i])
                except ValueError:
                    break
                i += 1
        else:
            i += count
    return ' '.join(parts[i:])


def image_read(path,maximum=4096):
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    size = reader.size()
    if size.isValid() and max(size.width(),size.height()) > maximum:
        size.scale(QSize(maximum,maximum),Qt.AspectRatioMode.KeepAspectRatio)
        reader.setScaledSize(size)
    image = reader.read()
    if image.isNull():
        # Pillow covers common modelling sidecars (notably TGA/DDS) that the
        # installed Qt image plugins may not decode.
        try:
            from PIL import Image,ImageOps
            from PyQt6.QtGui import QImage
            with Image.open(path) as source:
                picture=ImageOps.exif_transpose(source);picture.thumbnail((maximum,maximum));picture=picture.convert('RGBA')
                raw=picture.tobytes();image=QImage(raw,picture.width,picture.height,picture.width*4,QImage.Format.Format_RGBA8888).copy()
        except Exception as exc:raise ValueError(f'Cannot decode texture {path.name}: {reader.errorString()} / {exc}') from exc
    return image


def find_companion_texture(model,material=''):
    """Only unambiguous base-colour names; never guess from unrelated images."""
    import re
    model=Path(model)
    normalize=lambda value:re.sub(r'[^a-z0-9]','',value.casefold())
    candidates=[]
    for folder in (model.parent,model.parent/'textures',model.parent/'Textures'):
        if not folder.is_dir():continue
        for path in folder.iterdir():
            if path.is_file() and path.suffix.lower() in ('.png','.jpg','.jpeg','.webp','.bmp','.tga','.dds'):
                if path not in candidates:candidates.append(path)
    # Material-specific maps outrank a model atlas, which outranks generic names.
    for prefix in (normalize(material),normalize(model.stem),''):
        # A bare model-name image is often a catalogue render, not a UV atlas.
        # Only a material reference or an explicit map suffix establishes intent.
        suffixes=('albedo','basecolor','diffuse','color','d')
        if prefix and prefix==normalize(material) and prefix!=normalize(model.stem):suffixes=('',)+suffixes
        wanted={prefix+suffix for suffix in suffixes} if prefix else {'basecolor','albedo','diffuse'}
        matches=[path for path in candidates if normalize(path.stem) in wanted]
        if matches:return matches[0] if len(matches)==1 else None
    return None


def load_materials(obj,root,warnings):
    materials = {'':{'color':(0.35,0.5,0.55),'image':None,'texture_alpha':False}}
    libraries = []
    with obj.open(encoding='utf-8',errors='replace') as stream:
        for line in stream:
            if line.lstrip().startswith('mtllib '):
                value = line.strip()[7:].strip()
                # A single library with spaces is commonly unquoted.
                if (obj.parent/value).is_file():
                    libraries.append(value)
                else:
                    libraries.extend(tokens(value))
    for filename in libraries:
        try:
            mtl = dependency(obj.parent,filename,root)
            if not mtl.is_file():
                warnings.append(f'Missing material library: {filename}')
                continue
            if mtl.stat().st_size==0:
                warnings.append(f'Empty material library: {filename}; assign the model’s diffuse textures in Assets')
                continue
            if mtl.stat().st_size > 4_000_000:
                warnings.append(f'Material library too large: {filename}')
                continue
            current = None
            for line in mtl.read_text(encoding='utf-8',errors='replace').splitlines():
                parts = line.strip().split(maxsplit=1)
                if len(parts) != 2:
                    continue
                key,value = parts
                if key == 'newmtl':
                    current = materials.setdefault(value,{'color':(1,1,1),'image':None,'texture_alpha':False})
                elif current is not None and key == 'Kd':
                    color = tuple(float(v) for v in value.split()[:3])
                    if len(color) == 3 and all(math.isfinite(v) for v in color):
                        current['color'] = tuple(max(0,min(1,v)) for v in color)
                elif current is not None and key in ('d','Tr'):
                    alpha = float(value.split()[-1])
                    if math.isfinite(alpha):
                        current['opacity'] = max(0,min(1,alpha if key=='d' else 1-alpha))
                elif current is not None and key in ('map_Kd','map_Bump','map_bump','bump','norm'):
                    path = dependency(mtl.parent,map_filename(value),root)
                    current['texture_path'] = str(path)
                    if path.is_file():
                        try:
                            current['image' if key=='map_Kd' else 'normal_image'] = image_read(path)
                        except ValueError as exc:
                            warnings.append(str(exc))
                    else:
                        warnings.append(f'Missing texture: {path.name}')
        except (OSError,ValueError) as exc:
            warnings.append(str(exc))
    return materials


def load_obj(path,rotation=(0,0,0),root=None,texture=None,prefer_materials=False):
    path = Path(path).resolve()
    root = Path(root or path.parent).resolve()
    if path.stat().st_size > 96_000_000:
        raise ValueError('OBJ exceeds 96 MB; export a lighter preview model')
    vertices,uvs,faces,explicit_edges = [],[],[],[]
    vertex_normals,face_normal_refs=[],[]
    material = ''
    warnings = []
    def index(value,count):
        n = int(value)
        if n == 0:
            raise ValueError('OBJ indices cannot be zero')
        return n-1 if n > 0 else count+n
    with path.open(encoding='utf-8',errors='replace') as stream:
        for line_number,line in enumerate(stream,1):
            if len(line) > 65536:
                raise ValueError('OBJ polygon line too large')
            parts = line.split('#',1)[0].split()
            if not parts:
                continue
            if parts[0] == 'v':
                v = tuple(float(n) for n in parts[1:4])
                if len(v) != 3 or not all(math.isfinite(n) for n in v):
                    raise ValueError(f'Invalid vertex at line {line_number}')
                vertices.append(v)
            elif parts[0] == 'vt':
                uv = tuple(float(n) for n in parts[1:3])
                if len(uv) != 2 or not all(math.isfinite(n) for n in uv):
                    raise ValueError('Invalid UV coordinates')
                uvs.append(uv)
            elif parts[0]=='vn':
                normal=tuple(float(n) for n in parts[1:4])
                if len(normal)!=3 or not all(math.isfinite(n) for n in normal):raise ValueError('Invalid OBJ normal')
                vertex_normals.append(normal)
            elif parts[0] == 'usemtl':
                material = ' '.join(parts[1:])
            elif parts[0] in ('f','l'):
                refs = []
                normal_refs=[]
                for token in parts[1:]:
                    fields = token.split('/')
                    refs.append((index(fields[0],len(vertices)),
                                 index(fields[1],len(uvs)) if len(fields)>1 and fields[1] else None))
                    normal_refs.append(index(fields[2],len(vertex_normals)) if len(fields)>2 and fields[2] else None)
                if parts[0] == 'f':
                    for i in range(1,len(refs)-1):
                        faces.append((refs[0],refs[i],refs[i+1],material))
                        face_normal_refs.append((normal_refs[0],normal_refs[i],normal_refs[i+1]))
                else:
                    explicit_edges.extend((a[0],b[0]) for a,b in zip(refs,refs[1:]))
            if len(vertices)>500000 or len(faces)>300000 or len(uvs)>1000000 or len(vertex_normals)>1000000 or len(explicit_edges)>300000:
                raise ValueError('Model exceeds preview limits (500k vertices / 300k triangles)')
    if not vertices or not (faces or explicit_edges):
        raise ValueError('OBJ needs vertices and faces or lines')
    lo = [min(v[i] for v in vertices) for i in range(3)]
    hi = [max(v[i] for v in vertices) for i in range(3)]
    span = max(hi[i]-lo[i] for i in range(3))
    if span <= 1e-12:
        raise ValueError('Model has no visible size')
    if len(rotation)!=3 or not all(math.isfinite(float(v)) for v in rotation):
        raise ValueError('Rotation needs three finite angles')
    angles = [(math.cos(math.radians(float(a))),math.sin(math.radians(float(a)))) for a in rotation]
    normalized = []
    for v in vertices:
        x,y,z = [(v[i]-(lo[i]+hi[i])/2)*3/span for i in range(3)]
        c,s = angles[0]; y,z = y*c-z*s,y*s+z*c
        c,s = angles[1]; x,z = x*c+z*s,-x*s+z*c
        c,s = angles[2]; x,y = x*c-y*s,x*s+y*c
        normalized.append((x,y,z))
    materials = load_materials(path,root,warnings)
    for name,material in materials.items():
        if material['image'] is None:
            candidate=find_companion_texture(path,name)
            if candidate:material['image']=image_read(candidate);material['color']=(1,1,1)
    override_image = image_read(texture) if texture else None
    if override_image is not None:
        for m in materials.values():
            if not prefer_materials or m['image'] is None:m['image'] = override_image
    batches,triangles,edges = {},[],set()
    preview_step = max(1,math.ceil(len(faces)/400))
    for face_number,(a,b,c,mat) in enumerate(faces):
        refs = (a,b,c)
        if any(v<0 or v>=len(normalized) or uv is not None and (uv<0 or uv>=len(uvs)) for v,uv in refs):
            raise ValueError('Face references an invalid vertex or UV index')
        points = [normalized[v] for v,uv in refs]
        texcoords = [uvs[uv] if uv is not None else (0,0) for v,uv in refs]
        va,vb,vc = points
        x1,y1,z1 = [vb[i]-va[i] for i in range(3)]
        x2,y2,z2 = [vc[i]-va[i] for i in range(3)]
        normal = (y1*z2-z1*y2,z1*x2-x1*z2,x1*y2-y1*x2)
        norm = math.sqrt(sum(n*n for n in normal)) or 1
        normal = tuple(n/norm for n in normal)
        has_uv = all(uv is not None for v,uv in refs)
        if mat not in materials:
            candidate=find_companion_texture(path,mat)
            image=image_read(candidate) if candidate else override_image
            materials[mat]={'color':(1,1,1) if image is not None else (.55,.6,.65),'image':image,'texture_alpha':False}
        key = (mat,has_uv)
        batch = batches.setdefault(key,array('f'))
        for corner,(v,uv) in enumerate(zip(points,texcoords)):
            normal_index=face_normal_refs[face_number][corner]
            corner_normal=normal
            if normal_index is not None:
                if normal_index<0 or normal_index>=len(vertex_normals):raise ValueError('Face references an invalid normal')
                x,y,z=vertex_normals[normal_index]
                c,s=angles[0];y,z=y*c-z*s,y*s+z*c
                c,s=angles[1];x,z=x*c+z*s,-x*s+z*c
                c,s=angles[2];x,y=x*c-y*s,x*s+y*c
                corner_normal=(x,y,z)
            batch.extend((*v,*uv,*corner_normal))
        if face_number%preview_step==0:
            triangles.append((tuple(points),tuple(texcoords),mat,has_uv))
        edges.update(tuple(sorted((refs[i][0],refs[(i+1)%3][0]))) for i in range(3))
    for a,b in explicit_edges:
        if min(a,b)<0 or max(a,b)>=len(normalized):
            raise ValueError('Line references an invalid vertex')
        edges.add(tuple(sorted((a,b))))
    edges = sorted(edges)
    segments = [(normalized[a],normalized[b]) for a,b in edges[::max(1,math.ceil(len(edges)/1200))]]
    preview_edges = segments
    preview_triangles = triangles
    radius = max(math.sqrt(sum(n*n for n in v)) for v in normalized)
    if any(m['image'] is not None for m in materials.values()) and not any(t[3] for t in triangles):
        warnings.append('Textures found, but the OBJ has no usable UV coordinates')
    return ModelScene(normalized,triangles,segments,materials,batches,warnings,radius,len(faces),preview_triangles,preview_edges)


def import_model_bundle(filename,assets_root):
    """Copy OBJ + referenced MTL/maps with relative paths intact, never sibling files wholesale."""
    source = Path(filename).resolve()
    if not source.is_file() or source.suffix.lower() not in MODEL_FORMATS:
        raise ValueError('Select OBJ, GLB, glTF, STL, PLY or OFF')
    if source.stat().st_size>96_000_000:
        raise ValueError('OBJ exceeds 96 MB; export a lighter preview model')
    scene=read_mesh_scene(source) if source.suffix.lower()!='.obj' else None
    folder = Path(assets_root)/'models'/(uuid.uuid4().hex[:8]+'-'+source.stem)
    folder.mkdir(parents=True)
    if source.suffix.lower()!='.obj':
        # Canonical GLB embeds external buffers/textures for portable imports.
        target=folder/(source.stem+'.glb')
        target.write_bytes(scene.export(file_type='glb'))
        return target.relative_to(Path(assets_root)).as_posix(),[]
    warnings = []
    shutil.copy2(source,folder/source.name)
    libraries = []
    with source.open(encoding='utf-8',errors='replace') as stream:
        for line in stream:
            if line.lstrip().startswith('mtllib '):
                value = line.strip()[7:]
                libraries.extend([value] if (source.parent/value).is_file() else tokens(value))
    total_bytes = source.stat().st_size
    def copy_reference(base,value):
        nonlocal total_bytes
        path = dependency(base,value,source.parent)
        if not path.is_file():
            warnings.append(f'Missing resource: {value}')
            return None
        limit = 4_000_000 if path.suffix.lower()=='.mtl' else 96_000_000
        if path.stat().st_size>limit or total_bytes+path.stat().st_size>256_000_000:
            warnings.append(f'Resource too large: {path.name}')
            return None
        target = folder/path.relative_to(source.parent)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target)
        total_bytes += path.stat().st_size
        return path
    for value in libraries:
        try:
            mtl = copy_reference(source.parent,value)
            if not mtl:
                continue
            for line in mtl.read_text(encoding='utf-8',errors='replace').splitlines():
                parts = line.strip().split(maxsplit=1)
                if len(parts)==2 and parts[0].lower().startswith(('map_','bump','disp','decal','norm')):
                    try:
                        copy_reference(mtl.parent,map_filename(parts[1]))
                    except ValueError as exc:
                        warnings.append(str(exc))
        except ValueError as exc:
            warnings.append(str(exc))
    names={''}
    with source.open(encoding='utf-8',errors='replace') as stream:
        for line in stream:
            if line.lstrip().startswith('usemtl '):names.add(line.strip()[7:])
    for name in names:
        candidate=find_companion_texture(source,name)
        if candidate:
            try:copy_reference(source.parent,candidate.relative_to(source.parent).as_posix())
            except ValueError as exc:warnings.append(str(exc))
    relative = (folder/source.name).relative_to(Path(assets_root)).as_posix()
    return relative,warnings
