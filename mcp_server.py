#!/usr/bin/env python3
"""MCP server exposing baseball text-to-SQL tools."""

import json
import os
import sqlite3
from typing import Any

from mcp.server.fastmcp import FastMCP
from openai import OpenAI

GPT_MODEL = "gpt-4o-mini"
DB_PATH = "baseball_db.db"

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
conn = sqlite3.connect(DB_PATH)

# Curated examples for SQL generation.
EXAMPLE_QUERIES = [
    (
        "what players who played at Stanford were inducted into the hall of fame?",
        "SELECT DISTINCT p.nameFirst, p.nameLast, h.yearID FROM People p JOIN HallofFame h ON p.playerID = h.playerID JOIN CollegePlaying c ON p.playerID = c.playerID JOIN Schools s ON c.schoolID = s.schoolID WHERE s.schoolID= 'stanford' AND h.inducted = 'Y'",
    ),
    (
        "who are the all time Blue Jay home run leaders, and how many homers did they hit?",
        "SELECT people.nameFirst, people.nameLast, SUM(batting.HR) as homeRuns FROM batting JOIN people ON batting.playerID = people.playerID WHERE batting.teamID = 'TOR' GROUP BY people.playerID ORDER BY homeRuns DESC LIMIT 5;",
    ),
    (
        "in what seasons did teams have 4 or more 20-game winning pitchers? Who were the teams?",
        "SELECT Teams.name, Teams.yearID, COUNT(Pitching.W) as twenty_game_winners FROM Pitching JOIN Teams ON Pitching.teamID = Teams.teamID AND Pitching.yearID = Teams.yearID WHERE Pitching.W >= 20 GROUP BY Teams.teamID, Teams.yearID HAVING twenty_game_winners >= 4;",
    ),
    (
        "what 10 players have the most extra-base hits in world series play?",
        'SELECT People.nameFirst, People.nameLast, SUM(BattingPost."2B" + BattingPost."3B" + BattingPost.HR) as extra_base_hits FROM BattingPost JOIN People ON BattingPost.playerID = People.playerID WHERE BattingPost.round = \'WS\' GROUP BY People.playerID ORDER BY extra_base_hits DESC LIMIT 10;',
    ),
    (
        "Which players stole 50 or more bases in a season, and in what year?",
        "SELECT p.nameFirst, p.nameLast, b.yearID, b.SB FROM Batting b JOIN People p ON b.playerID = p.playerID WHERE b.SB >= 50 ORDER BY b.SB DESC, b.yearID ASC;",
    ),
    (
        "Which teams won at least 100 games in a season?",
        "SELECT yearID, teamID, name, W FROM Teams WHERE W >= 100 ORDER BY W DESC, yearID ASC;",
    ),
    (
        "Which Hall of Fame inductees were pitchers with at least 300 career wins?",
        "SELECT p.nameFirst, p.nameLast, SUM(pi.W) as career_wins FROM HallofFame h JOIN People p ON h.playerID = p.playerID JOIN Pitching pi ON p.playerID = pi.playerID WHERE h.inducted = 'Y' GROUP BY p.playerID HAVING career_wins >= 300 ORDER BY career_wins DESC;",
    ),
]

SCHEMA_SNIPPET = """
Main tables:
- People(playerID, nameFirst, nameLast, birthYear, birthCountry, ...)
- Teams(yearID, teamID, name, W, L, ...)
- Batting(playerID, yearID, teamID, H, HR, RBI, SB, BB, SO, ...)
- Pitching(playerID, yearID, teamID, W, SV, SO, ...)
- HallofFame(playerID, yearID, inducted)
- AwardsPlayers(playerID, yearID, awardID)
- Appearances(playerID, yearID, teamID)
- Schools(schoolID, name_full)
- CollegePlaying(playerID, schoolID)
- BattingPost(playerID, yearID, round, "2B", "3B", HR)
""".strip()


def _build_prompt(question: str) -> str:
    example_block = "\n".join([f"({json.dumps(q)}, {json.dumps(sql)})" for q, sql in EXAMPLE_QUERIES])
    return (
        "Generate one valid SQLite SQL query to answer the user's baseball question. "
        "Return SQL only, no markdown or explanation.\n\n"
        f"{SCHEMA_SNIPPET}\n\n"
        "Here are sample correct queries in the format (input, query):\n"
        f"{example_block}\n\n"
        f"User question: {question}"
    )


def _generate_sql(question: str) -> str:
    response = client.chat.completions.create(
        model=GPT_MODEL,
        messages=[{"role": "user", "content": _build_prompt(question)}],
        temperature=0,
    )
    return response.choices[0].message.content.strip()


def _ask_database(query: str) -> list[tuple[Any, ...]]:
    return conn.execute(query).fetchall()


mcp = FastMCP("baseball-text2sql")


@mcp.tool()
def generate_sql(question: str) -> str:
    """Generate SQL for a baseball question using curated examples and schema hints."""
    return _generate_sql(question)


@mcp.tool()
def query_database(query: str) -> str:
    """Run a SQL query against the baseball SQLite database and return rows."""
    try:
        return json.dumps(_ask_database(query))
    except Exception as e:
        return f"query failed with error: {e}"


@mcp.tool()
def answer_question(question: str) -> str:
    """Generate SQL and execute it against the baseball database."""
    sql = _generate_sql(question)
    try:
        rows = _ask_database(sql)
        return json.dumps({"sql": sql, "rows": rows})
    except Exception as e:
        return json.dumps({"sql": sql, "error": str(e)})


if __name__ == "__main__":
    mcp.run()
