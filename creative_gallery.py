"""Interactive creative application examples for Workshop and plugins."""
import math
import random
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QLineEdit, QListWidget, QListWidgetItem, QInputDialog, QCheckBox, QProgressBar, QTabWidget, QComboBox, QTableWidget, QTableWidgetItem

EXPERIENCES={
 'constellation':('Constellation playground','Click to place stars; proximity creates a living network.'),
 'particles':('Particle reactor','Click to release particles; tune the simulation speed.'),
 'waves':('Wave synthesizer','Explore interference patterns and tune their frequency.'),
 'orbit':('Orbital observatory','A miniature animated solar system with adjustable time.'),
 'life':('Cellular life lab','Paint cells, step generations and discover emergent patterns.'),
 'mandala':('Generative mandala','Explore radial symmetry and save a unique composition.'),
 'rain':('Digital rain','An ambient typography installation with motion controls.'),
 'terrain':('Terrain hologram','Explore an animated procedural landscape.'),
 'focus':('Focus garden','Grow a visual garden through timed focus sessions.'),
 'story':('Branching story studio','Choose your path through an interactive story.'),
 'kanban':('Idea constellation board','Organize creative ideas across a movable three-column board.'),
 'palette':('Palette laboratory','Generate color harmonies and copy individual colors.'),
}

class CreativeCanvas(QWidget):
    def __init__(self,mode):
        super().__init__();self.mode=mode;self.tick=0;self.speed=1;self.running=True;self.seed=random.random()*10
        self.points=[(random.random(),random.random()) for _ in range(35)]
        self.particles=[];self.cells={(random.randrange(36),random.randrange(22)) for _ in range(110)}
        self.setMinimumSize(300,260);self.setMouseTracking(True)
        self.timer=QTimer(self);self.timer.timeout.connect(self.advance)
    def showEvent(self,event): self.timer.start(40);super().showEvent(event)
    def hideEvent(self,event): self.timer.stop();super().hideEvent(event)
    def advance(self):
        if not self.running:return
        self.tick+=self.speed
        if self.mode=='life' and int(self.tick)%8==0:self.step_life()
        self.particles=[(x+vx,y+vy,vx,vy+.0002,age-1) for x,y,vx,vy,age in self.particles if age>0]
        self.update()
    def step_life(self):
        counts={}
        for x,y in self.cells:
            for dx in (-1,0,1):
                for dy in (-1,0,1):
                    if dx or dy:
                        pos=((x+dx)%36,(y+dy)%22);counts[pos]=counts.get(pos,0)+1
        self.cells={pos for pos,n in counts.items() if n==3 or n==2 and pos in self.cells};self.update()
    def mousePressEvent(self,event):
        x,y=event.position().x()/self.width(),event.position().y()/self.height()
        if self.mode=='life':
            cell=(min(35,int(x*36)),min(21,int(y*22)))
            if cell in self.cells:self.cells.remove(cell)
            else:self.cells.add(cell)
        elif self.mode=='particles':
            self.particles += [(x,y,math.cos(a)*.009,math.sin(a)*.009,100) for a in [i*math.tau/48 for i in range(48)]]
            self.particles=self.particles[-1200:]
        else:self.points.append((x,y));self.points=self.points[-100:]
        self.update()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing);p.fillRect(self.rect(),QColor('#081219'))
        w,h=self.width(),self.height();t=self.tick*.02;cyan=QColor('#26d8ee');orange=QColor('#ff7b1c')
        p.setPen(QPen(cyan,1))
        if self.mode=='life':
            p.setPen(QPen(QColor('#18323d'),1))
            for x in range(37):p.drawLine(int(x*w/36),0,int(x*w/36),h)
            for y in range(23):p.drawLine(0,int(y*h/22),w,int(y*h/22))
            for x,y in self.cells:p.fillRect(QRectF(x*w/36+1,y*h/22+1,w/36-2,h/22-2),cyan)
        elif self.mode=='constellation':
            for i,(x,y) in enumerate(self.points):
                for xx,yy in self.points[i+1:]:
                    d=math.hypot(x-xx,y-yy)
                    if d<.2:p.setPen(QColor(38,216,238,int((1-d/.2)*150)));p.drawLine(QPointF(x*w,y*h),QPointF(xx*w,yy*h))
                p.setPen(cyan);p.setBrush(cyan);p.drawEllipse(QPointF(x*w,y*h),3+math.sin(t+i),3+math.sin(t+i))
        elif self.mode=='particles':
            for x,y,vx,vy,age in self.particles:
                p.setPen(QColor(255,120+min(100,age),40,min(255,age*3)));p.drawEllipse(QPointF(x*w,y*h),3,3)
        elif self.mode=='waves':
            for layer in range(6):
                p.setPen(QColor(38+layer*30,216-layer*15,238,180))
                last=None
                for x in range(0,w,4):
                    point=QPointF(x,h/2+math.sin(x*.015*self.speed+t+layer*.5)*h*.17+math.sin(x*.027-t)*h*.09)
                    if last is not None:p.drawLine(last,point)
                    last=point
        elif self.mode=='orbit':
            center=QPointF(w/2,h/2);p.setBrush(orange);p.drawEllipse(center,22,22);p.setBrush(Qt.BrushStyle.NoBrush)
            for i in range(1,7):
                r=min(w,h)*(.065+i*.055);p.setPen(QColor('#264653'));p.drawEllipse(center,r,r)
                a=t/(i*.6)+i;p.setBrush(cyan);p.setPen(cyan);p.drawEllipse(QPointF(w/2+math.cos(a)*r,h/2+math.sin(a)*r),4+i,4+i);p.setBrush(Qt.BrushStyle.NoBrush)
        elif self.mode=='mandala':
            center=QPointF(w/2,h/2)
            for layer in range(1,10):
                r=min(w,h)*layer*.045
                for i in range(18):
                    a=i*math.tau/18+t*.08+layer*.2;p.setPen(QColor.fromHsv((layer*24+int(self.seed*20))%360,180,240,170))
                    p.drawEllipse(QPointF(center.x()+math.cos(a)*r,center.y()+math.sin(a)*r),layer*2,layer*2)
        elif self.mode=='rain':
            p.setFont(self.font())
            for col in range(max(1,w//18)):
                for row in range(14):
                    y=(self.tick*(2+col%4)+row*20+col*31)%(h+280)-140
                    p.setPen(QColor(38,216,180,max(20,240-row*16)));p.drawText(col*18,int(y),chr(33+(col*7+row*13)%90))
        elif self.mode=='terrain':
            for row in range(18):
                last=None;p.setPen(QColor(38,150+row*5,238,90+row*8))
                for col in range(40):
                    x=w*.1+col*w*.8/39;y=h*.15+row*h*.038+math.sin(col*.3+row*.4+t)*h*.045
                    point=QPointF(x,y)
                    if last is not None:p.drawLine(last,point)
                    last=point
        p.end()

class CreativePage(QWidget):
    def __init__(self,mode,ctx=None):
        super().__init__();self.mode=mode;self.ctx=ctx;title,description=EXPERIENCES[mode];root=QVBoxLayout(self)
        heading=QLabel(title.upper());heading.setStyleSheet('font-size:22px;font-weight:bold;color:#26d8ee;');root.addWidget(heading)
        subtitle=QLabel(description);subtitle.setWordWrap(True);root.addWidget(subtitle)
        if mode in ('focus','story','kanban','palette'):self.build_special(root)
        else:
            self.canvas=CreativeCanvas(mode);root.addWidget(self.canvas,1);actions=QHBoxLayout();root.addLayout(actions)
            pause=QPushButton('Pause / resume');pause.clicked.connect(lambda:setattr(self.canvas,'running',not self.canvas.running));actions.addWidget(pause)
            reset=QPushButton('Remix');reset.clicked.connect(self.remix);actions.addWidget(reset)
            slider=QSlider(Qt.Orientation.Horizontal);slider.setRange(1,8);slider.setValue(1);slider.valueChanged.connect(lambda v:setattr(self.canvas,'speed',v));actions.addWidget(slider,1)
            export=QPushButton('Export artwork');export.clicked.connect(self.export_art);actions.addWidget(export)
            if mode=='life':
                step=QPushButton('Step generation');step.clicked.connect(self.canvas.step_life);actions.addWidget(step)
    def remix(self):
        self.canvas.seed=random.random()*10;self.canvas.points=[(random.random(),random.random()) for _ in range(35)];self.canvas.cells={(random.randrange(36),random.randrange(22)) for _ in range(110)};self.canvas.update()
    def export_art(self):
        from PyQt6.QtWidgets import QFileDialog
        path,_=QFileDialog.getSaveFileName(self,'Export artwork','','PNG image (*.png)')
        if path:self.canvas.grab().save(path,'PNG')
    def build_special(self,root):
        if self.mode=='palette':
            self.swatches=QHBoxLayout();root.addLayout(self.swatches);b=QPushButton('Generate harmony');b.clicked.connect(self.palette);root.addWidget(b);self.palette()
        elif self.mode=='kanban':
            row=QHBoxLayout();root.addLayout(row,1);self.boards=[]
            for title in ('Seeds','Growing','Harvested'):
                col=QVBoxLayout();row.addLayout(col);col.addWidget(QLabel(title));board=QListWidget();board.setSelectionMode(QListWidget.SelectionMode.SingleSelection);board.setDragDropMode(QListWidget.DragDropMode.DragDrop);board.setDefaultDropAction(Qt.DropAction.MoveAction);col.addWidget(board);self.boards.append(board)
            self.input=QLineEdit();self.input.setPlaceholderText('New idea');root.addWidget(self.input);b=QPushButton('Plant idea');b.clicked.connect(self.add_idea);root.addWidget(b)
            self.boards[0].addItems(['Interactive story','Visual instrument','Tiny world simulator'])
        elif self.mode=='story':
            self.chapter=QLabel();self.chapter.setWordWrap(True);self.chapter.setStyleSheet('font-size:24px;padding:30px;');root.addWidget(self.chapter,1)
            self.choices=QVBoxLayout();root.addLayout(self.choices);self.story('start')
        else:
            self.remaining=25*60;self.focus_running=False;self.clock=QLabel('25:00');self.clock.setStyleSheet('font-size:64px;color:#26d8ee;');root.addWidget(self.clock,1)
            self.garden=QLabel('Seeds planted: 0');root.addWidget(self.garden);self.sessions=0
            b=QPushButton('Start / pause focus');b.clicked.connect(lambda:setattr(self,'focus_running',not self.focus_running));root.addWidget(b)
            reset=QPushButton('Reset session');reset.clicked.connect(self.reset_focus);root.addWidget(reset)
            self.timer=QTimer(self);self.timer.timeout.connect(self.focus_tick);self.timer.start(1000)
    def reset_focus(self):self.remaining=1500;self.focus_running=False;self.clock.setText('25:00')
    def focus_tick(self):
        if not self.focus_running:return
        self.remaining=max(0,self.remaining-1);self.clock.setText(f'{self.remaining//60:02}:{self.remaining%60:02}')
        if not self.remaining:self.sessions+=1;self.garden.setText('🌱 '*self.sessions);self.reset_focus()
    def add_idea(self):
        if self.input.text().strip():self.boards[0].addItem(self.input.text().strip());self.input.clear()
    def palette(self):
        from PyQt6.QtWidgets import QApplication
        while self.swatches.count():self.swatches.takeAt(0).widget().deleteLater()
        hue=random.randrange(360)
        for offset in (0,30,150,180,210):
            color=QColor.fromHsv((hue+offset)%360,160,220).name();b=QPushButton(color);b.setMinimumHeight(160);b.setStyleSheet('background:'+color+';color:#ffffff;border:0;');b.clicked.connect(lambda checked=False,c=color:QApplication.clipboard().setText(c));self.swatches.addWidget(b)
    def story(self,node):
        chapters={'start':('A signal arrives from an abandoned orbital garden.', [('Investigate the signal','garden'),('Follow the stars','stars')]),'garden':('The garden remembers every visitor. A seed glows in your hand.', [('Plant the seed','bloom'),('Return to the station','start')]),'stars':('The stars form a map to a world you have imagined.', [('Build a new world','bloom'),('Follow the signal','garden')]),'bloom':('A new constellation blooms. Your next story begins here.', [('Begin again','start')])}
        text,choices=chapters[node];self.chapter.setText(text)
        while self.choices.count():self.choices.takeAt(0).widget().deleteLater()
        for title,target in choices:
            b=QPushButton(title);b.clicked.connect(lambda checked=False,n=target:self.story(n));self.choices.addWidget(b)
