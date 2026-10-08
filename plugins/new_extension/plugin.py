def register(ctx):
    from creative_gallery import CreativePage
    page=CreativePage('terrain',ctx)
    ctx.add_page('Terrain hologram',page)
    ctx.add_template('Terrain hologram','from pylerium_gui import create_application, AppWindow, button, label, panel, run, configure_audio, play_cue\nfrom creative_gallery import CreativePage\n\nclass MyWindow(AppWindow):\n    def __init__(self):\n        super().__init__(\'Terrain hologram\')\n        self.content.addWidget(CreativePage(\'terrain\'),1)\n\ndef main():\n    app = create_application("My application")\n    # Opt in to shared hover, click and task completion cues.\n    # configure_audio(enabled=True, volume=18)\n    window = MyWindow()\n    return run(window)\n\nif __name__ == "__main__":\n    raise SystemExit(main())\n')
