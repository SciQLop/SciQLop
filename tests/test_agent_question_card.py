def test_question_card_collects_single_and_multi_answers(qtbot):
    # qtbot provides a QApplication so importing the agents.chat package
    # (transitive SciQLopPlots bindings) does not abort headless.
    from PySide6.QtWidgets import QCheckBox, QPushButton
    from SciQLop.components.agents.chat.question_card import QuestionCard

    questions = [
        {"question": "Format?", "header": "Fmt",
         "options": [{"label": "Summary", "description": "brief"},
                     {"label": "Detailed"}], "multiSelect": False},
        {"question": "Sections?", "header": "Sec",
         "options": [{"label": "Intro"}, {"label": "Concl"}], "multiSelect": True},
    ]
    card = QuestionCard(questions)
    qtbot.addWidget(card)

    captured = {}
    card.answered.connect(lambda a: captured.update(a))

    for cb in card.findChildren(QCheckBox):   # check both multi-select boxes
        cb.setChecked(True)
    card.findChild(QPushButton, "agentQuestionSend").click()

    assert captured["Format?"] == "Summary"               # single-select defaults to first
    assert set(captured["Sections?"]) == {"Intro", "Concl"}  # multi-select collects checked


def test_question_card_single_select_respects_user_choice(qtbot):
    from PySide6.QtWidgets import QPushButton, QRadioButton
    from SciQLop.components.agents.chat.question_card import QuestionCard

    card = QuestionCard([
        {"question": "Pick", "options": [{"label": "A"}, {"label": "B"}],
         "multiSelect": False},
    ])
    qtbot.addWidget(card)
    captured = {}
    card.answered.connect(lambda a: captured.update(a))

    radios = card.findChildren(QRadioButton)
    radios[1].setChecked(True)   # choose B over the default A
    card.findChild(QPushButton, "agentQuestionSend").click()

    assert captured["Pick"] == "B"


def test_long_option_descriptions_wrap_instead_of_being_cropped(qtbot):
    """Qt buttons never wrap their own text, so a long description has to live
    in a label of its own or it is silently cut off at the dock's width."""
    from PySide6.QtWidgets import QLabel, QRadioButton
    from SciQLop.components.agents.chat.question_card import QuestionCard

    description = ("Copies the transcript into SciQLop's own store so it "
                   "survives the CLI's 30-day cleanup, and restores it on "
                   "resume — a long line that must not be cropped.")
    card = QuestionCard([
        {"question": "How far?", "options": [{"label": "Archive", "description": description}]},
    ])
    qtbot.addWidget(card)

    button = card.findChildren(QRadioButton)[0]
    assert button.text() == "Archive"  # the button carries the label alone

    labels = [w for w in card.findChildren(QLabel) if w.text() == description]
    assert labels and labels[0].wordWrap()


def test_a_long_question_still_wraps(qtbot):
    from PySide6.QtWidgets import QLabel
    from SciQLop.components.agents.chat.question_card import QuestionCard

    question = "Which retention strategy should SciQLop use for agent sessions?"
    card = QuestionCard([{"question": question, "options": [{"label": "A"}]}])
    qtbot.addWidget(card)

    labels = [w for w in card.findChildren(QLabel) if w.text() == question]
    assert labels and labels[0].wordWrap()


def test_an_option_without_a_description_adds_no_label(qtbot):
    from PySide6.QtWidgets import QLabel
    from SciQLop.components.agents.chat.question_card import QuestionCard

    card = QuestionCard([{"question": "Pick", "options": [{"label": "A"}, {"label": "B"}]}])
    qtbot.addWidget(card)

    assert [w.text() for w in card.findChildren(QLabel)] == ["Pick"]
