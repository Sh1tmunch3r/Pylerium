"""Opt-in, reusable GUI audio. One engine per QApplication, bounded cue rates."""
import time
from pathlib import Path
from PyQt6.QtCore import QObject, QEvent, QUrl, pyqtSignal
from PyQt6.QtWidgets import QApplication, QAbstractButton, QTabBar, QMenuBar

CUES=('hover','click','deploy','success','error')

class UIAudio(QObject):
    played=pyqtSignal(str)
    def __init__(self,app,root):
        super().__init__(app);self.root=Path(root);self.enabled=False;self.volume=.18
        self.settings={};self.players={};self.last={};self.hover_targets={};self.problem='';app.installEventFilter(self)
        app.aboutToQuit.connect(self.shutdown)

    def shutdown(self):
        self.enabled=False
        QApplication.instance().removeEventFilter(self)
        for player,output in self.players.values():player.stop()

    def configure(self,settings):
        self.settings=dict(settings);self.enabled=bool(settings.get('audio_enabled',False))
        self.volume=max(0,min(100,int(settings.get('audio_volume',18))))/100
        if not self.enabled:
            for player,output in self.players.values():player.stop()
        for player,output in self.players.values():
            (output or player).setVolume(self.volume)
        if self.enabled:
            for cue in CUES:
                if self.settings.get('audio_'+cue,True):
                    source=self.source(cue)
                    if source is not None:
                        try:self.prepare(source)
                        except (ImportError,RuntimeError,OSError) as error:self.problem=str(error)

    def source(self,cue):
        custom=self.settings.get('audio_'+cue+'_file','')
        if custom and Path(custom).is_file():return Path(custom)
        # UI cues should use predecoded effects rather than seek/restart a media decoder.
        names=('hover_button.wav','hover.wav','hover_button.mp3') if cue=='hover' else (cue+'.wav',cue+'.mp3')
        return next((self.root/name for name in names if (self.root/name).is_file()),None)

    def play(self,cue):
        if cue not in CUES or not self.enabled or not self.settings.get('audio_'+cue,True):return False
        now=time.monotonic();interval=.12 if cue=='hover' else .08
        if now-self.last.get(cue,0)<interval:return False
        source=self.source(cue)
        if source is None:return False
        self.last[cue]=now
        try:
            player,_=self.prepare(source)
            if source.suffix.lower()!='.wav':
                from PyQt6.QtMultimedia import QMediaPlayer
                if player.playbackState()==QMediaPlayer.PlaybackState.PlayingState:
                    return False
                if player.mediaStatus()==QMediaPlayer.MediaStatus.EndOfMedia:
                    player.setPosition(0)
            player.play();self.played.emit(cue);return True
        except (ImportError,RuntimeError,OSError) as error:
            self.problem=str(error);return False

    def prepare(self,source):
        key=str(source)
        if key not in self.players:
            from PyQt6.QtMultimedia import QSoundEffect,QMediaPlayer,QAudioOutput
            if source.suffix.lower()=='.wav':
                player=QSoundEffect(self);output=None;player.setVolume(self.volume)
            else:
                player=QMediaPlayer(self);output=QAudioOutput(self);output.setVolume(self.volume);player.setAudioOutput(output)
            player.setSource(QUrl.fromLocalFile(str(source.resolve())))
            if len(self.players)>=16:
                old,old_output=self.players.pop(next(iter(self.players)))
                old.stop();old.deleteLater()
                if old_output:old_output.deleteLater()
            self.players[key]=(player,output)
        return self.players[key]

    def eventFilter(self,obj,event):
        if not self.enabled:return False
        if event.type()==QEvent.Type.Enter:
            if isinstance(obj,(QTabBar,QMenuBar)) or isinstance(obj,QAbstractButton) and (obj.isCheckable() or obj.property('audio_hover')):
                if obj.isEnabled():self.play('hover')
        elif event.type()==QEvent.Type.MouseMove and isinstance(obj,(QTabBar,QMenuBar)):
            target=obj.tabAt(event.position().toPoint()) if isinstance(obj,QTabBar) else obj.actionAt(event.position().toPoint())
            if target!=self.hover_targets.get(id(obj)):
                self.hover_targets[id(obj)]=target;self.play('hover')
        elif event.type()==QEvent.Type.MouseButtonRelease and isinstance(obj,QAbstractButton) and obj.isEnabled():
            self.play('click')
        return False


def audio_engine():
    app=QApplication.instance()
    if app is None:raise RuntimeError('Create QApplication before using UI audio')
    if not hasattr(app,'_pylerium_audio'):
        from asset_helper import ASSETS
        app._pylerium_audio=UIAudio(app,ASSETS.root/'audio')
    return app._pylerium_audio

def play_cue(cue):return audio_engine().play(cue)

def configure_audio(enabled=False,volume=18,**options):
    from PyQt6.QtCore import QSettings
    import json
    engine=audio_engine();settings={**options,'audio_enabled':enabled,'audio_volume':volume}
    engine.configure(settings)
    QSettings('Pylerium',QApplication.instance().applicationName()).setValue('audio/options',json.dumps(settings))
    return engine
