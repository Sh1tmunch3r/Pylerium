"""Static, asynchronously rendered artwork for execution cards."""
import math
from PyQt6.QtCore import QObject, pyqtSignal, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QLinearGradient
from asset_helper import ASSETS, AssetTask
from model_renderer import SoftwareModelRenderer

class ThumbnailLibrary(QObject):
    changed=pyqtSignal(str)
    def __init__(self):
        super().__init__(); self.frames={}; self.errors={}; self.tasks={}; self.waiting=set(); self.generation=0
        ASSETS.model_ready.connect(self.loaded); ASSETS.invalidated.connect(self.clear)
    def clear(self):
        self.generation+=1; self.frames.clear(); self.errors.clear(); self.waiting.clear(); self.changed.emit('')
    def request(self,key):
        if key in self.frames or key in self.errors or key in self.waiting: return
        self.waiting.add(key); ASSETS.request_model(key)
    def loaded(self,key,scene,error):
        if key not in self.waiting: return
        self.waiting.discard(key)
        if error or scene is None:
            self.errors[key]=error or ''; self.changed.emit(key); return
        token=(self.generation,key)
        if token in self.tasks: return
        def render():
            image=SoftwareModelRenderer(scene).render(640,300,.7,-.18,1.0,framing=max(1,scene.radius))[0]
            import numpy as np
            rgba=image.convertToFormat(image.Format.Format_RGBA8888)
            bits=rgba.constBits();bits.setsize(rgba.sizeInBytes())
            pixels=np.frombuffer(bits,dtype=np.uint8).reshape(rgba.height(),rgba.bytesPerLine())[:,:rgba.width()*4].reshape(rgba.height(),rgba.width(),4)
            ys,xs=np.nonzero(pixels[:,:,3]>8)
            if len(xs):
                left=max(0,int(xs.min())-8);top=max(0,int(ys.min())-8)
                right=min(image.width(),int(xs.max())+9);bottom=min(image.height(),int(ys.max())+9)
                image=image.copy(left,top,right-left,bottom-top)
            return image
        task=AssetTask(token,render);self.tasks[token]=task;task.signals.finished.connect(self.finished);ASSETS.pool.start(task)
    def finished(self,token,image,error):
        self.tasks.pop(token,None)
        if token[0]!=self.generation:return
        if image is not None:self.frames[token[1]]=image
        else:self.errors[token[1]]=error
        while len(self.frames)>48:self.frames.pop(next(iter(self.frames)))
        self.changed.emit(token[1])

THUMBNAILS=ThumbnailLibrary()

def card_class(base):
    class ExecutionCard(base):
        def __init__(self,data,kind):
            super().__init__(data,kind); self.setMouseTracking(True)
            THUMBNAILS.changed.connect(self.art_changed)
            self.setToolTip(data.description+'\nRight-click to assign image or static 3D artwork.')
        def art_changed(self,key):
            if not key or key==self.item_data.asset_key:self.update()
        def paintEvent(self,event):
            p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
            r=QRectF(self.rect()).adjusted(1,1,-1,-1)
            gradient=QLinearGradient(r.topLeft(),r.bottomRight());gradient.setColorAt(0,QColor('#18232b'));gradient.setColorAt(1,QColor('#0a1015'))
            p.fillRect(r,gradient);p.setPen(QPen(QColor('#f06413' if self.selected or self.hover_progress else '#34444e'),1));p.drawRoundedRect(r,4,4)
            p.fillRect(QRectF(2,2,3,self.height()-4),QColor('#f06413' if self.selected else '#26d8ee'))
            p.setFont(QFont('Arial',9,QFont.Weight.Bold));p.setPen(QColor('#96abb6'))
            p.drawText(QRectF(16,10,self.width()-32,22),Qt.AlignmentFlag.AlignLeft,self.item_data.category)
            key=self.item_data.asset_key;entry=ASSETS.entry(key);art=QRectF(16,38,self.width()-32,max(24,self.height()-99))
            if entry.get('model'):
                THUMBNAILS.request(key);frame=THUMBNAILS.frames.get(key)
                if frame is not None:
                    ratio=min(art.width()/frame.width(),art.height()/frame.height());target=QRectF(0,0,frame.width()*ratio,frame.height()*ratio);target.moveCenter(art.center());p.drawImage(target,frame)
                else:
                    p.setPen(QColor('#7894a3'));p.drawText(art,Qt.AlignmentFlag.AlignCenter,'MODEL UNAVAILABLE' if THUMBNAILS.errors.get(key) else 'LOADING MODEL…')
            elif not ASSETS.paint_image(p,art,entry.get('icon')):
                p.setPen(QPen(QColor(38,216,238,65),1));center=art.center()
                p.drawEllipse(center,16,16);p.drawLine(int(center.x()-25),int(center.y()),int(center.x()+25),int(center.y()));p.drawLine(int(center.x()),int(center.y()-25),int(center.x()),int(center.y()+25))
            p.setFont(QFont('Arial',12,QFont.Weight.Bold));p.setPen(QColor('#edf4f7'))
            text=p.fontMetrics().elidedText(self.item_data.name,Qt.TextElideMode.ElideRight,max(1,self.width()-32))
            p.drawText(QRectF(16,self.height()-53,self.width()-32,24),Qt.AlignmentFlag.AlignLeft,text)
            p.setFont(QFont('Arial',9));p.setPen(QColor('#76919f'))
            text=p.fontMetrics().elidedText(self.item_data.description.split('\n')[0],Qt.TextElideMode.ElideRight,max(1,self.width()-32))
            p.drawText(QRectF(16,self.height()-29,self.width()-32,19),Qt.AlignmentFlag.AlignLeft,text)
            p.end()
    return ExecutionCard
