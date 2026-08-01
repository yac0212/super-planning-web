# -*- coding: utf-8 -*-
"""Scenarios de test. Module sans effet de bord : importable sans muter la base."""

JOUR_PLEIN = {
    "AIT ELHADJ Sonia":  {"ms": "09:00", "me": "13:00", "aes": "14:00", "aee": "18:00"},
    "AYACHE Yacine":     {"ms": "09:00", "me": "13:00", "aes": "14:00", "aee": "19:00"},
    "BARDON Maia":       {"ms": "", "me": "", "aes": "15:00", "aee": "20:00"},
    "BECHICHI Dalya":    {"ms": "09:00", "me": "14:00", "aes": "", "aee": ""},
    "BERTHE Sebastien":  {"ms": "10:00", "me": "13:30", "aes": "14:30", "aee": "19:00"},
    "BRASSAC Alexandra": {"ms": "09:00", "me": "13:00", "aes": "", "aee": ""},
    "CHARPENTIER Nora":  {"ms": "", "me": "", "aes": "13:00", "aee": "20:00"},
    "COLONDON Ethan":    {"ms": "09:00", "me": "13:00", "aes": "14:00", "aee": "18:30"},
    "GOURGEOIS Nathalie":{"ms": "09:30", "me": "13:00", "aes": "14:00", "aee": "19:00"},
    "Interimaire 1":     {"ms": "10:00", "me": "14:00", "aes": "", "aee": ""},
    "Interimaire 2":     {"ms": "", "me": "", "aes": "15:00", "aee": "20:00"},
    "KIATA Corneille":   {"ms": "", "me": "", "aes": "16:00", "aee": "20:00"},
    "MIATOLOKA Cecilia": {"ms": "09:00", "me": "13:00", "aes": "14:00", "aee": "19:00"},
    "MOYSAN Christelle": {"ms": "09:00", "me": "13:30", "aes": "", "aee": ""},
    "NEJMI Anas":        {"ms": "11:00", "me": "14:00", "aes": "15:00", "aee": "20:00"},
    "PIERQUIN Alicia":   {"ms": "09:00", "me": "13:00", "aes": "14:00", "aee": "17:00"},
    "POWELL Laura":      {"ms": "", "me": "", "aes": "14:00", "aee": "20:00"},
    "SY Diariata":       {"ms": "09:00", "me": "13:00", "aes": "14:00", "aee": "19:00"},
}

EFFECTIF_REDUIT = {k: JOUR_PLEIN[k] for k in list(JOUR_PLEIN)[:9]}

AVEC_HANDICAP = dict(JOUR_PLEIN)
AVEC_HANDICAP["SOUSA MARTINS André"] = {"ms": "09:00", "me": "13:00", "aes": "14:00", "aee": "19:00"}

SCENARIOS = [
    ("Jeudi - effectif plein",  "30/07/2026", JOUR_PLEIN),
    ("Jeudi - effectif reduit", "30/07/2026", EFFECTIF_REDUIT),
    ("Dimanche",                "02/08/2026", JOUR_PLEIN),
    ("Jeudi + restr. handicap", "30/07/2026", AVEC_HANDICAP),
]
