import photovault.photo_organiser as organiser


def test_plans_move_into_location_folder():
    photos = [{'filename': 'a.heic', 'location': 'Angus, Scotland'}]

    moves = organiser.plan_moves(photos)

    assert moves == [('a.heic', 'Angus, Scotland/a.heic')]


def test_skips_photos_without_location_or_already_in_folders():
    photos = [
        {'filename': 'no_gps.jpg'},
        {'filename': 'Fife, Scotland/sorted.heic', 'location': 'Fife, Scotland'},
    ]

    moves = organiser.plan_moves(photos)

    assert moves == []


def test_pairs_go_into_their_own_folder_named_after_the_photo():
    photos = [{
        'filename': 'a.heic',
        'location': 'Angus, Scotland',
        'videoFilename': 'clip.mov',
    }]

    moves = organiser.plan_moves(photos)

    assert moves == [
        ('a.heic', 'Angus, Scotland/a/a.heic'),
        ('clip.mov', 'Angus, Scotland/a/clip.mov'),
    ]


def test_moves_an_existing_location_pair_into_its_own_folder():
    photos = [{
        'filename': 'North Berwick, Scotland/a.heic',
        'location': 'North Berwick, Scotland',
        'videoFilename': 'North Berwick, Scotland/clip.mov',
    }]

    moves = organiser.plan_moves(photos)

    assert moves == [
        ('North Berwick, Scotland/a.heic', 'North Berwick, Scotland/a/a.heic'),
        ('North Berwick, Scotland/clip.mov', 'North Berwick, Scotland/a/clip.mov'),
    ]


def test_pair_already_in_its_folder_is_left_alone():
    photos = [{
        'filename': 'Angus, Scotland/a/a.heic',
        'location': 'Angus, Scotland',
        'videoFilename': 'Angus, Scotland/a/clip.mov',
    }]

    moves = organiser.plan_moves(photos)

    assert moves == []


def test_folder_names_never_contain_path_separators():
    photos = [{'filename': 'a.heic', 'location': 'Some/Odd\\Place'}]

    moves = organiser.plan_moves(photos)

    assert moves == [('a.heic', 'Some-Odd-Place/a.heic')]


def test_organise_runs_one_rclone_move_per_planned_file(monkeypatch):
    commands = []
    monkeypatch.setattr(organiser, '_run_rclone', lambda args: commands.append(args))
    photos = [{'filename': 'a.heic', 'location': 'Angus, Scotland'}]

    moved = organiser.organise('gdrive:PhotoFrame', photos)

    assert moved == 1
    assert commands == [[
        'moveto',
        'gdrive:PhotoFrame/a.heic',
        'gdrive:PhotoFrame/Angus, Scotland/a.heic',
    ]]


def test_organise_carries_on_after_a_failed_move(monkeypatch):
    def flaky(args):
        if 'a.heic' in args[1]:
            raise RuntimeError('rclone failed')

    monkeypatch.setattr(organiser, '_run_rclone', flaky)
    photos = [
        {'filename': 'a.heic', 'location': 'Angus, Scotland'},
        {'filename': 'b.heic', 'location': 'Fife, Scotland'},
    ]

    moved = organiser.organise('gdrive:PhotoFrame', photos)

    assert moved == 1


def test_run_rclone_surfaces_the_rclone_error(monkeypatch):
    class Completed:
        returncode = 1
        stderr = 'notice: making dir\nreason: insufficient permission'

    monkeypatch.setattr(organiser.subprocess, 'run', lambda *a, **k: Completed())

    try:
        organiser._run_rclone(['moveto', 'a', 'b'])
        raised = False
    except RuntimeError as e:
        raised = 'insufficient permission' in str(e)

    assert raised
