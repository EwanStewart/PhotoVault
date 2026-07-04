import photovault.main as main


def test_serve_runs_app_under_threaded_wsgi_server(monkeypatch):
    calls = {}

    def fake_serve(app, **kwargs):
        calls['app'] = app
        calls.update(kwargs)

    monkeypatch.setattr(main.waitress, 'serve', fake_serve)

    main.serve()

    assert calls['app'] is main.app
    assert calls['port'] == 5000
    assert calls['threads'] > 1
