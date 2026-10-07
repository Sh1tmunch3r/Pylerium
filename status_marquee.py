"""Live file-backed tags and terminal-styled workspace events."""
import time,re,math
from collections import deque
from PyQt6.QtCore import QTimer,Qt
from PyQt6.QtGui import QPainter,QColor,QFont,QStaticText,QLinearGradient,QPen,QBrush
from PyQt6.QtWidgets import QWidget
from ultimate_terminal import Terminal,Style,RGB


class StatusMarquee(QWidget):
    def __init__(self,path,parent=None):
        super().__init__(parent);self.path=path;self.tags=[];self.events=deque(maxlen=100);self.pending=deque(maxlen=100)
        self.index=0;self.style_index=0;self.current='PYLERIUM // READY';self.offset=0.;self.speed=45;self.enabled=True;self.pause_hover=True
        self.cycle_styles=True;self.hovered=False;self.stamp=None;self.last=time.monotonic();self.terminal=Terminal();self.animation="Gradient";self.cache=None;self.phase=0.
        self.setFixedHeight(25);self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setFont(QFont('Consolas',10))
        self.timer=QTimer(self);self.timer.timeout.connect(self.advance);self.timer.start(33)
        self.watcher=QTimer(self);self.watcher.timeout.connect(self.reload_tags);self.watcher.start(2000);self.reload_tags()

    def reload_tags(self):
        try:
            stamp=(self.path.stat().st_mtime_ns,self.path.stat().st_size)
            if stamp==self.stamp:return
            lines=self.path.read_text(encoding='utf-8-sig').splitlines()
            self.tags=list(dict.fromkeys(line.strip() for line in lines if line.strip() and not line.lstrip().startswith('#')))
            self.stamp=stamp;self.index=0
        except (OSError,UnicodeError):self.tags=[];self.stamp=None

    def setText(self,text):
        text=re.sub(r'\x1b\[[0-9;]*m','',str(text)).replace('\n',' ').strip()
        if not text:return
        self.events.append(text);self.current=text[:4000];self.offset=0;self.cache=None
        self.setToolTip('\n'.join(self.events));self.update()

    def text(self):return self.current

    def configure(self,settings,styles=None):
        self.speed=settings.get('marquee_speed',45);self.enabled=settings.get('marquee_scroll',True)
        self.pause_hover=settings.get('marquee_pause_hover',True);self.cycle_styles=settings.get('marquee_styles',True)
        self.animation=settings.get('marquee_animation','Gradient');self.timer.setInterval(round(1000/max(10,min(60,settings.get('marquee_fps',30)))))
        self.cache=None
        self.terminal.set_theme(settings.get('output_theme','cyber'))
        for name,config in (styles or {}).items():
            try:
                config=dict(config)
                for key in ('foreground','background'):
                    if config.get(key):config[key]=RGB.from_hex(config[key])
                self.terminal.add_style(name,Style(**config))
            except (ValueError,TypeError):continue
        self.update()

    def advance(self):
        now=time.monotonic();dt=min(now-self.last,.1);self.last=now
        if not self.isVisible() or self.window().isMinimized() or not self.enabled or self.hovered and self.pause_hover:return
        self.phase+=dt
        self.ensure_cache()
        self.offset-=self.speed*dt
        if self.offset+self.cached_width<0:
            if self.pending:self.current=self.pending.popleft()
            elif self.tags:self.current=self.tags[self.index%len(self.tags)];self.index+=1
            elif self.events:self.current=self.events[-1]
            else:self.current='PYLERIUM // READY'
            self.style_index+=1;self.offset=self.width();self.cache=None
        self.update()

    def enterEvent(self,event):self.hovered=True;super().enterEvent(event)
    def leaveEvent(self,event):self.hovered=False;super().leaveEvent(event)

    def hideEvent(self,event):
        self.timer.stop();super().hideEvent(event)

    def showEvent(self,event):
        self.last=time.monotonic();self.timer.start();super().showEvent(event)

    def ensure_cache(self):
        if self.cache is not None:return
        names=list(self.terminal.styles);name=names[self.style_index%len(names)] if self.cycle_styles and names else 'info'
        upper=self.current.upper()
        if any(word in upper for word in ('FAILED','ERROR')):name='error'
        elif any(word in upper for word in ('SAVED','COMPLETE','SUCCEEDED')):name='success'
        elif any(word in upper for word in ('WARNING','REVIEW','STOPPED')):name='warning'
        self.semantic=name in ('error','success','warning')
        self.style=self.terminal.get_style(name) or Style()
        font=QFont(self.font());font.setBold(self.style.bold);font.setItalic(self.style.italic)
        font.setUnderline(self.style.underline);font.setStrikeOut(self.style.strike)
        self.cached_font=font;self.cache=QStaticText(self.current)
        self.cache.setTextFormat(Qt.TextFormat.PlainText);self.cache.prepare(font=font)
        self.cached_width=self.cache.size().width()
        palettes=list(self.terminal.GRADIENTS.values())
        self.palette=[QColor(value) for value in palettes[self.style_index%len(palettes)]]

    def paintEvent(self,event):
        self.ensure_cache();painter=QPainter(self);painter.setClipRect(self.rect());style=self.style
        def colour(value,fallback):return QColor(value.r,value.g,value.b) if value else QColor(fallback)
        foreground=colour(style.foreground,'#26d8ee');background=colour(style.background,'#0b1115')
        if style.reverse:foreground,background=background,foreground
        if style.background or style.reverse:painter.fillRect(self.rect(),background)
        painter.setFont(self.cached_font);painter.setPen(foreground)
        opacity=.6 if style.dim else 1.
        if style.blink:opacity*=.55+.45*math.sin(self.phase*math.pi)**2
        if self.animation=='Pulse':opacity*=.65+.35*math.sin(self.phase*2)**2
        if self.animation in ('Gradient','Rainbow','Scanner') and not self.semantic:
            shift=math.sin(self.phase*.8)*self.width()*.2
            gradient=QLinearGradient(shift,0,self.width()+shift,0)
            colours=self.palette if self.animation!='Rainbow' else [QColor(c) for c in self.terminal.GRADIENTS['rainbow']]
            if self.animation=='Scanner':colours=[foreground,QColor('#ffffff'),foreground]
            for i,c in enumerate(colours):gradient.setColorAt(i/max(1,len(colours)-1),c)
            painter.setPen(QPen(QBrush(gradient),1))
        painter.setOpacity(opacity)
        painter.drawStaticText(int(self.offset if self.enabled else 0),int((self.height()-self.cache.size().height())/2),self.cache)
