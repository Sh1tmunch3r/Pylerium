def register(ctx):
    from creative_gallery import CreativePage
    page=CreativePage('life',ctx)
    ctx.add_page('Cellular life lab',page)
    ctx.add_template('Cellular life lab','from pylerium_gui import create_application, AppWindow, button, label, panel, run, configure_audio, play_cue\nfrom creative_gallery import CreativePage\n\nclass MyWindow(AppWindow):\n    def __init__(self):\n        super().__init__(\'Cellular life lab\')\n        self.content.addWidget(CreativePage(\'life\'),1)\n\ndef main():\n    app = create_application("My application")\n    # Opt in to shared hover, click and task completion cues.\n    # configure_audio(enabled=True, volume=18)\n    window = MyWindow()\n    return run(window)\n\nif __name__ == "__main__":\n    raise SystemExit(main())\n')
