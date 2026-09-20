from image_gen_controller.questions import QUESTION_SPECS, build_sdk_questions


def test_question_specs_use_typesafe_shapes():
    assert QUESTION_SPECS["policy_violation"]["type"] == "noul"
    assert set(QUESTION_SPECS["policy_violation"]["criteria"]) == {"true", "false"}
    assert QUESTION_SPECS["specificity"]["criteria"][0].startswith("Unusable")
    assert set(QUESTION_SPECS["next_action"]["criteria"]) == {
        "block",
        "ask_clarify",
        "allow_lite",
        "allow_premium",
    }


def test_sdk_questions_construct():
    questions = build_sdk_questions()
    assert set(questions) == {"policy_violation", "specificity", "next_action"}
    assert questions["policy_violation"].type == "noul"
    assert questions["specificity"].type == "score"
    assert questions["next_action"].type == "choice"
