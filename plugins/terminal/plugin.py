
def register(ctx):
    from PyQt6.QtWidgets import QWidget,QVBoxLayout
    from status_marquee import StatusMarquee
    from asset_helper import ASSETS
    page=QWidget();box=QVBoxLayout(page);marquee=StatusMarquee(ASSETS.root/'tags.txt')
    marquee.configure(ctx.window.settings,ctx.window.plugin_styles)
    ctx.on('run_finished',lambda ident,status:marquee.setText(f'{status.upper()} // {ident[:8]}'))
    box.addWidget(marquee);box.addStretch();ctx.add_page('Events',page)
