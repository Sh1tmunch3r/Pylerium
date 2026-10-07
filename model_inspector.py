"""Large shared weapon inspection studio with camera, turntable and material views."""
import math
from PyQt6.QtCore import Qt,QVariantAnimation,QEasingCurve
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QSplitter,QWidget,QComboBox,QCheckBox,QSlider,QListWidget,QLabel,QScrollArea
from gui_components import STYLE,button,label
from model_preview import InteractiveModelCanvas


class InspectWeaponDialog(QDialog):
    def __init__(self,source,parent=None):
        scene_snapshot=source.scene;item_snapshot=source.item_data
        super().__init__(parent);self.setWindowTitle('Inspect weapon / model');self.setStyleSheet(STYLE)
        self.resize(1440,940);self.setMinimumSize(960,650);self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.source=source;self.canvas=InteractiveModelCanvas();self.canvas.paused=True
        self.canvas.timer.setInterval(16);self.animation=QVariantAnimation(self);self.animation.setDuration(5000)
        self.animation.setStartValue(0.0);self.animation.setEndValue(1.0);self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.animation.valueChanged.connect(self.inspect_frame)
        root=QVBoxLayout(self);header=QHBoxLayout()
        header.addWidget(label('INSPECT // '+getattr(source.item_data,'name','Model').upper(),26));header.addStretch()
        header.addWidget(button('SAVE PREVIEW',self.canvas.export_preview));header.addWidget(button('CLOSE',self.close));root.addLayout(header)
        split=QSplitter();split.addWidget(self.canvas);side=QWidget();tools=QVBoxLayout(side);side.setMaximumWidth(320)
        tools.addWidget(label('CAMERA',19));views=QComboBox();views.addItems(['Perspective','Front','Back','Left','Right','Top'])
        cameras=[(.7,-.18),(0,0),(math.pi,0),(-math.pi/2,0),(math.pi/2,0),(0,math.pi/2)]
        views.currentIndexChanged.connect(lambda index:self.camera(*cameras[index]));tools.addWidget(views)
        tools.addWidget(button('INSPECT / 360°',self.start_inspect,True));tools.addWidget(button('FIT MODEL',self.canvas.reset_view))
        orbit=QCheckBox('Auto orbit');orbit.toggled.connect(self.set_orbit);tools.addWidget(orbit)
        wire=QCheckBox('Wireframe');wire.toggled.connect(lambda checked:self.set_wireframe(checked));tools.addWidget(wire)
        grid=QCheckBox('Floor grid');grid.setChecked(True);grid.toggled.connect(lambda checked:self.set_grid(checked));tools.addWidget(grid)
        tools.addWidget(label('ZOOM',12));zoom=QSlider(Qt.Orientation.Horizontal);zoom.setRange(20,400);zoom.setValue(100)
        zoom.valueChanged.connect(lambda value:self.set_zoom(value/100));tools.addWidget(zoom)
        quality=QComboBox();quality.addItems(['Native / 4× MSAA','Studio / up to 4K','Fast']);quality.currentIndexChanged.connect(lambda index:self.canvas.set_quality([2560,4096,960][index]));tools.addWidget(quality)
        tools.addWidget(label('MATERIALS / TEXTURES',19));self.materials=QListWidget();tools.addWidget(self.materials)
        self.details=label('',11,'#9aabb4');tools.addWidget(self.details)
        self.thumbnail=QLabel();self.thumbnail.setMinimumHeight(120);self.thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter);tools.addWidget(self.thumbnail)
        self.materials.currentRowChanged.connect(self.select_material);self.materials.itemDoubleClicked.connect(self.open_texture)
        tools.addStretch();split.addWidget(side);split.setSizes([1100,300]);root.addWidget(split,1)
        self.status=label('Preparing full-resolution inspection…',11,'#26d8ee');root.addWidget(self.status)
        root.addWidget(label('Drag to orbit • Right/middle drag to pan • Wheel to zoom • F to fit • Space to pause • Double-click a material to inspect its texture',11,'#9aabb4'))
        self.canvas.model_status.connect(self.scene_changed)
        if item_snapshot:self.canvas.set_item(item_snapshot)
        if scene_snapshot and item_snapshot:self.canvas.loaded(getattr(item_snapshot,'asset_key',item_snapshot.name),scene_snapshot,'')
        self.canvas.set_camera(.7,-.18);self.scene_changed(self.canvas.message)

    def scene_changed(self,text):
        self.status.setText(text)
        scene=self.canvas.scene
        if scene is None or getattr(self,'listed_scene',None) is scene:return
        self.listed_scene=scene;self.material_keys=list(scene.materials);self.materials.clear()
        for key in self.material_keys:
            mat=scene.materials[key];image=mat.get('image')
            self.materials.addItem(mat.get('name',key)+' ['+key+']'+(' // '+str(image.width())+'×'+str(image.height()) if image is not None else ' // solid colour'))
        if self.material_keys:self.materials.setCurrentRow(0)

    def select_material(self,index):
        if index<0 or self.canvas.scene is None:return
        mat=self.canvas.scene.materials[self.material_keys[index]];image=mat.get('image')
        self.details.setText('Base colour '+str(mat.get('color'))+'\nNormal map: '+('yes' if mat.get('normal_image') is not None else 'no')+'\nMetal/roughness map: '+('yes' if mat.get('orm_image') is not None else 'no'))
        self.thumbnail.clear()
        if image is not None:self.thumbnail.setPixmap(QPixmap.fromImage(image).scaled(280,170,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))

    def open_texture(self,*_):
        index=self.materials.currentRow()
        if index<0:return
        image=self.canvas.scene.materials[self.material_keys[index]].get('image')
        if image is None:return
        dialog=QDialog(self);dialog.setWindowTitle('Texture // '+self.material_keys[index]);dialog.resize(900,750)
        layout=QVBoxLayout(dialog);scroll=QScrollArea();picture=QLabel();picture.setPixmap(QPixmap.fromImage(image));scroll.setWidget(picture);layout.addWidget(scroll)
        dialog.exec()

    def camera(self,rotation,elevation):
        self.animation.stop();self.canvas.set_camera(rotation,elevation)

    def set_orbit(self,enabled):
        self.animation.stop();self.canvas.paused=not enabled;self.canvas.surface_key=None;self.canvas.update()

    def set_wireframe(self,enabled):
        self.canvas.textured=not enabled;self.canvas.update()

    def set_grid(self,enabled):
        self.canvas.show_grid=enabled;self.canvas.update()

    def set_zoom(self,value):
        self.canvas.zoom=value;self.canvas.update()

    def start_inspect(self):
        self.canvas.paused=True;self.inspect_rotation=self.canvas.rotation;self.animation.stop();self.animation.start()

    def inspect_frame(self,value):
        self.canvas.rotation=self.inspect_rotation+float(value)*math.tau
        self.canvas.elevation=-.18+.12*math.sin(float(value)*math.tau)
        self.canvas.update()

    def closeEvent(self,event):
        self.animation.stop();self.canvas.shutdown_renderer();super().closeEvent(event)
