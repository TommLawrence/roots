"""Learner personas for the synthetic cohort.

Each persona is a function (skill, term_index) -> expected mean score 0-100.
Term index: 0 = Y1T1 .. 11 = Y4T3. Fixed personas land on L001-L005 so the
evals can assert on them deterministically.
"""

SKILLS = {
    "math": ["geometry", "arithmetic"],
    "english": ["reading", "writing"],
    "science": ["reasoning"],
}
ALL_SKILLS = {"geometry": "math", "arithmetic": "math", "reading": "english",
              "writing": "english", "reasoning": "science"}


def steady_high(skill, ti):
    return 85 + (1 if ti % 3 == 2 else 0)


def declining_reader(skill, ti):
    if skill == "reading":
        return 76 - max(0, ti - 3) * 4.5
    return 72


def hidden_spatial(skill, ti):
    if skill == "geometry":
        return 86 + (ti % 4) - 1
    if skill == "reading":
        return 55
    return 68


def attendance_crises(skill, ti):
    base = 70
    # Y3T1 is term index 6; scores dip during the attendance crisis window
    if 6 <= ti <= 7:
        return base - 13
    return base + (2 if ti > 7 else 0)


def late_bloomer(skill, ti):
    return 55 + max(0, ti - 6) * 3.5


def noisy_average(skill, ti):
    return 68


PERSONAS = {
    "steady_high": steady_high,
    "declining_reader": declining_reader,
    "hidden_spatial": hidden_spatial,
    "attendance_crises": attendance_crises,
    "late_bloomer": late_bloomer,
    "noisy_average": noisy_average,
}

# Fixed assignment for the deterministic eval learners
FIXED = ["steady_high", "declining_reader", "hidden_spatial",
         "attendance_crises", "late_bloomer"]

NOTE_POOL = [
    "Good participation in group work today",
    "Struggled with the reading passage again",
    "Very neat handwriting this week",
    "Was absent on Friday, family responsibilities",
    "Asked for extra help with fractions",
    "Distracted during the morning session",
    "Helped a classmate with the shape activity",
    "Essay showed real improvement",
    "Did not finish the comprehension questions",
    "Bright in the mental maths warm-up",
]

KISWAHILI_NOTE_POOL = [
    "anasoma vizuri darasani",
    "anahitaji msaada wa kusoma kwa sauti",
    "anapenda hesabu na michezo",
    "hudhuriani mara nyingi lakini amechoka",
    "inandishi insha nzuri wiki hii",
]

GUARDIAN_TITLES = ("Mama", "Baba")
