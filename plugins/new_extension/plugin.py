def register(ctx):
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton
    page = QWidget()
    layout = QVBoxLayout(page)
    project = ctx.selector('project')
    profile = ctx.selector('profile')
    run = QPushButton('Run selected project')
    run.clicked.connect(lambda: ctx.window.safe(lambda: ctx.window.launch(project.currentData(), profile.currentData())))
    layout.addWidget(project)
    layout.addWidget(profile)
    layout.addWidget(run)
    ctx.add_page('Project launcher', page)
