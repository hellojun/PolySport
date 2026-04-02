"""
NBA固定本体定义
提供NBA比赛预测所需的实体类型和关系类型
"""

from typing import Dict, Any


def get_nba_ontology() -> Dict[str, Any]:
    """
    返回NBA固定本体，格式与 GraphBuilderService.set_ontology() 兼容。

    包含:
    - 10 个实体类型
    - 8 个关系类型
    """
    return {
        "entity_types": [
            {
                "name": "Team",
                "description": "NBA basketball team",
                "attributes": [
                    {"name": "abbreviation", "description": "Team abbreviation (e.g. LAL, BOS)"},
                    {"name": "conference", "description": "Eastern or Western conference"},
                    {"name": "record", "description": "Win-loss record"},
                ]
            },
            {
                "name": "Player",
                "description": "NBA player",
                "attributes": [
                    {"name": "position", "description": "Playing position (PG, SG, SF, PF, C)"},
                    {"name": "jersey_number", "description": "Jersey number"},
                    {"name": "stats_summary", "description": "Key stats summary (PPG, RPG, APG)"},
                ]
            },
            {
                "name": "Coach",
                "description": "NBA head coach or assistant coach",
                "attributes": [
                    {"name": "role", "description": "Head coach or assistant"},
                    {"name": "coaching_style", "description": "Coaching style description"},
                ]
            },
            {
                "name": "Arena",
                "description": "NBA arena or venue",
                "attributes": [
                    {"name": "city", "description": "City where the arena is located"},
                    {"name": "capacity", "description": "Seating capacity"},
                ]
            },
            {
                "name": "Injury",
                "description": "Player injury report entry",
                "attributes": [
                    {"name": "injury_type", "description": "Type of injury"},
                    {"name": "status", "description": "Out, Doubtful, Questionable, Probable, Available"},
                    {"name": "expected_return", "description": "Expected return date or timeline"},
                ]
            },
            {
                "name": "GameRecord",
                "description": "Historical game result",
                "attributes": [
                    {"name": "game_date", "description": "Date of the game"},
                    {"name": "score", "description": "Final score"},
                    {"name": "venue", "description": "Home or away"},
                ]
            },
            {
                "name": "Division",
                "description": "NBA division (e.g. Atlantic, Pacific)",
                "attributes": [
                    {"name": "conference", "description": "Parent conference"},
                ]
            },
            {
                "name": "Season",
                "description": "NBA season (e.g. 2024-25)",
                "attributes": [
                    {"name": "year", "description": "Season year"},
                    {"name": "phase", "description": "Regular season, Playoffs, Finals"},
                ]
            },
            {
                "name": "Person",
                "description": "General person entity (analyst, referee, etc.)",
                "attributes": [
                    {"name": "role", "description": "Role or title"},
                ]
            },
            {
                "name": "Organization",
                "description": "Organization (NBA league, media outlet, etc.)",
                "attributes": [
                    {"name": "org_type", "description": "Type of organization"},
                ]
            },
        ],
        "edge_types": [
            {
                "name": "PLAYS_FOR",
                "description": "Player plays for a team",
                "source_targets": [
                    {"source": "Player", "target": "Team"}
                ],
                "attributes": [
                    {"name": "contract_year", "description": "Whether player is in a contract year"},
                ]
            },
            {
                "name": "COACHES",
                "description": "Coach coaches a team",
                "source_targets": [
                    {"source": "Coach", "target": "Team"}
                ],
                "attributes": []
            },
            {
                "name": "HAS_INJURY",
                "description": "Player has an injury",
                "source_targets": [
                    {"source": "Player", "target": "Injury"}
                ],
                "attributes": []
            },
            {
                "name": "DEFEATED",
                "description": "Team defeated another team in a game",
                "source_targets": [
                    {"source": "Team", "target": "Team"}
                ],
                "attributes": [
                    {"name": "margin", "description": "Point differential"},
                    {"name": "game_date", "description": "Date of the game"},
                ]
            },
            {
                "name": "HOME_COURT",
                "description": "Team's home arena",
                "source_targets": [
                    {"source": "Team", "target": "Arena"}
                ],
                "attributes": []
            },
            {
                "name": "BELONGS_TO",
                "description": "Team belongs to a division",
                "source_targets": [
                    {"source": "Team", "target": "Division"}
                ],
                "attributes": []
            },
            {
                "name": "PLAYED_IN",
                "description": "Game was played in a season",
                "source_targets": [
                    {"source": "GameRecord", "target": "Season"}
                ],
                "attributes": []
            },
            {
                "name": "TEAMMATE",
                "description": "Two players are on the same team",
                "source_targets": [
                    {"source": "Player", "target": "Player"}
                ],
                "attributes": [
                    {"name": "chemistry", "description": "On-court chemistry description"},
                ]
            },
        ]
    }
