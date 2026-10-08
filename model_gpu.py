"""Qt-native GPU preview: one-time buffers, hardware depth and UV textures."""
import math
from array import array

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QMatrix4x4, QVector3D
from PyQt6.QtOpenGL import (QOpenGLBuffer,QOpenGLShader,QOpenGLShaderProgram,
                           QOpenGLTexture,QOpenGLVersionFunctionsFactory,QOpenGLVersionProfile)
from PyQt6.QtOpenGLWidgets import QOpenGLWidget


VERTEX = '''#version 120
attribute vec3 position;
attribute vec2 uv;
attribute vec3 normal;
uniform mat4 mvp;
uniform mat4 model;
varying vec2 texcoord;
varying vec3 surface_normal;
void main() {
    gl_Position = mvp * vec4(position,1.0);
    texcoord = uv;
    surface_normal = mat3(model) * normal;
}
'''
FRAGMENT = '''#version 120
uniform sampler2D surface;
uniform bool has_texture;
uniform bool line_mode;
uniform vec3 diffuse;
uniform float opacity;
varying vec2 texcoord;
varying vec3 surface_normal;
void main() {
    if (line_mode) { gl_FragColor = vec4(diffuse,0.65); return; }
    vec4 color = has_texture ? texture2D(surface,texcoord) : vec4(diffuse,1.0);
    float light = 0.45 + 0.55 * abs(dot(normalize(surface_normal), normalize(vec3(0.3,0.7,1.0))));
    gl_FragColor = vec4(color.rgb*light,color.a*opacity);
}
'''


class GpuModelView(QOpenGLWidget):
    failed = pyqtSignal(str)
    ready = pyqtSignal()

    def __init__(self,parent):
        super().__init__(parent)
        self.controller = parent
        self.scene = None
        self.pending = True
        self.program = None
        self.functions = None
        self.buffers = []
        self.textures = []
        self.floor = None
        self.lines = None
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_scene(self,scene):
        self.scene = scene
        self.pending = True
        self.update()

    def initializeGL(self):
        try:
            profile = QOpenGLVersionProfile()
            profile.setVersion(2,0)
            self.functions = QOpenGLVersionFunctionsFactory.get(profile,self.context())
            if self.functions is None:
                raise RuntimeError('OpenGL 2.0 functions unavailable')
            self.functions.initializeOpenGLFunctions()
            self.program = QOpenGLShaderProgram(self)
            if not self.program.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Vertex,VERTEX):
                raise RuntimeError(self.program.log())
            if not self.program.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Fragment,FRAGMENT):
                raise RuntimeError(self.program.log())
            if not self.program.link():
                raise RuntimeError(self.program.log())
            self.context().aboutToBeDestroyed.connect(self.cleanup)
            self.ready.emit()
        except Exception as exc:
            self.failed.emit(str(exc))

    def buffer(self,values):
        b = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
        if not b.create():
            raise RuntimeError('Cannot allocate GPU buffer')
        b.bind()
        raw = values.tobytes()
        b.allocate(raw,len(raw))
        b.release()
        return b

    def upload(self):
        self.release_resources()
        if not self.scene:
            return
        for key,values in self.scene.batches.items():
            mat,has_uv = key
            material = self.scene.materials[mat]
            texture = None
            image = material.get('image')
            if has_uv and image is not None:
                texture = QOpenGLTexture(image.mirrored())
                texture.setMinMagFilters(QOpenGLTexture.Filter.LinearMipMapLinear,QOpenGLTexture.Filter.Linear)
                texture.setWrapMode(QOpenGLTexture.WrapMode.Repeat)
                self.textures.append(texture)
            self.buffers.append((self.buffer(values),len(values)//8,material['color'],texture,material.get('opacity',1.0)))
        values = array('f')
        for a,b in self.scene.preview_edges:
            for v in (a,b):
                values.extend((*v,0,0,0,1,0))
        self.lines = (self.buffer(values),len(values)//8)
        values = array('f')
        floor_y = min(v[1] for v in self.scene.vertices)-0.08
        for i in range(-8,9):
            n = i*0.4
            for v in ((n,floor_y,-3.2),(n,floor_y,3.2),(-3.2,floor_y,n),(3.2,floor_y,n)):
                values.extend((*v,0,0,0,1,0))
        self.floor = (self.buffer(values),len(values)//8)

    def draw_buffer(self,b,count,mode,color,texture=None,line=False,opacity=1.0):
        p = self.program
        b.bind()
        for name,offset,size in [('position',0,3),('uv',12,2),('normal',20,3)]:
            p.enableAttributeArray(name)
            p.setAttributeBuffer(name,5126,offset,size,32)
        p.setUniformValue('diffuse',QVector3D(*color))
        p.setUniformValue('has_texture',texture is not None)
        p.setUniformValue('line_mode',line)
        p.setUniformValue('opacity',float(opacity))
        if texture:
            texture.bind(0)
        self.functions.glDrawArrays(mode,0,count)
        if texture:
            texture.release(0)
        b.release()

    def paintGL(self):
        if not self.program or not self.functions:
            return
        try:
            f = self.functions
            f.glClearColor(0.043,0.047,0.055,1)
            f.glClear(16384|256)
            if not self.scene:
                return
            if self.pending:
                self.upload()
                self.pending = False
            f.glEnable(2929)
            f.glEnable(3042)
            f.glBlendFunc(770,771)
            model = QMatrix4x4()
            model.rotate(math.degrees(self.controller.elevation),1,0,0)
            model.rotate(-math.degrees(self.controller.rotation),0,1,0)
            model.scale(self.controller.zoom)
            aspect = max(0.1,self.width()/max(1,self.height()))
            distance = self.scene.radius*1.22/(math.sin(math.radians(22.5))*min(1,aspect))
            view = QMatrix4x4()
            view.translate(0,0,-max(4.5,distance))
            projection = QMatrix4x4()
            projection.perspective(45,aspect,0.1,100)
            self.program.bind()
            self.program.setUniformValue('model',model)
            self.program.setUniformValue('mvp',projection*view*model)
            self.program.setUniformValue('surface',0)
            self.draw_buffer(*self.floor,1,(0.06,0.22,0.25),line=True)
            if self.controller.textured:
                for transparent in (False,True):
                    f.glDepthMask(not transparent)
                    for buffer,count,color,texture,opacity in self.buffers:
                        if (opacity<1.0) == transparent:
                            self.draw_buffer(buffer,count,4,color,texture,opacity=opacity)
                f.glDepthMask(True)
            else:
                self.draw_buffer(*self.lines,1,(0.22,0.85,0.93),line=True)
            self.program.release()
        except Exception as exc:
            self.failed.emit(str(exc))
            self.program = None

    def release_resources(self):
        for b,count,color,texture,opacity in self.buffers:
            b.destroy()
        self.buffers.clear()
        for texture in self.textures:
            texture.destroy()
        self.textures.clear()
        for item in (self.floor,self.lines):
            if item:
                item[0].destroy()
        self.floor,self.lines = None,None

    def cleanup(self):
        if self.context() and self.context().isValid():
            self.makeCurrent()
            self.release_resources()
            self.doneCurrent()
