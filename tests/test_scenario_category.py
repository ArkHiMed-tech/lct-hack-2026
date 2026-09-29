"""Маппинг категории сценария: Главная служба / раздел / legacy."""
from routers.reports import _scenario_category


def test_main_services():
    assert _scenario_category({"main_service": "MCHS"}, {})[0] == "fire"
    assert _scenario_category({"main_service": "Police"}, {})[0] == "police"
    assert _scenario_category({"main_service": "AMBULANCE"}, {})[0] == "ambulance"
    assert _scenario_category({"main_service": "MOSGAZ"}, {})[0] == "gas"


def test_utility_mains():
    for main in ("MOSLIFT", "MOEK", "OEK", "MOESK", "MOSVODOCANAL",
                 "MOSVODOSTOK", "MOSCOLLECTOR", "GORMOST", "GKH", "MGTS"):
        assert _scenario_category({"main_service": main}, {})[0] == "utility", main


def test_transport_mains_and_compound():
    for main in ("METRO", "MZD", "MOSGORTRANS", "AUTOROADS", "METRO, MZD"):
        assert _scenario_category({"main_service": main}, {})[0] == "dth", main


def test_section_fallback_and_legacy():
    assert _scenario_category(
        {"main_service": None, "classifier_section": {"g": 22}}, {})[0] == "ambulance"
    assert _scenario_category(
        {"main_service": None, "classifier_section": {"g": 14}}, {})[0] == "utility"
    assert _scenario_category(
        {"main_service": None, "classifier_section": {"g": 24}}, {})[0] == "police"
    assert _scenario_category({"incident_category": "101"}, {})[0] == "fire"
    assert _scenario_category({"incident_category": "103"}, {})[0] == "ambulance"
    category, label = _scenario_category(
        {"incident_category": "пожар на улице",
         "classifier_section": {"g": 1, "title": "Пожары и задымления"}}, {})
    assert (category, label) == ("fire", "пожар на улице")
