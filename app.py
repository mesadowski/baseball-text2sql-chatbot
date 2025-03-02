#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Mar 1 2025

@author: michaelsadowski
"""

import streamlit as st

from openai import OpenAI
from tenacity import retry, wait_random_exponential, stop_after_attempt
import json
import os

GPT_MODEL = 'gpt-4o-mini'

OPENAI_API_KEY = os.environ['OPENAI_API_KEY']  #you need to put your Open AI key in an environment variable is your OS

client = OpenAI(api_key= OPENAI_API_KEY)

import sqlite3

conn = sqlite3.connect('baseball_db.db')  # the .db file for the baseball database must be in the same directory as the python file for the streamlit app
print('Opened database successfully')   #TODO check that connection was actually successful

@retry(wait=wait_random_exponential(multiplier=1, max=40), stop=stop_after_attempt(3))
def chat_completion_request(messages, tools=None, tool_choice=None, model=GPT_MODEL):
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
        )
        return response
    except Exception as e:
        print("Unable to generate ChatCompletion response")
        print(f"Exception: {e}")
        return e
    
def ask_question_openai(question,tools,client):
    openai_messages = [{
    "role":"user", 
    "content": question}]
    
    response = client.chat.completions.create(
    model='gpt-4o', 
    messages=openai_messages, 
    tools= tools, 
    tool_choice="auto"
    )

    # Append the message to messages list
    response_message = response.choices[0].message 
    openai_messages.append(response_message)

    print(response_message)
    return response_message

def ask_database(conn, query):
    """Function to query SQLite database with a provided SQL query."""
    try:
        results = str(conn.execute(query).fetchall())
    except Exception as e:
        results = f"query failed with error: {e}"
    return results

# Open AI's tools feature lets us force OpenAI's output to be an input to another module. In this case we'll force it to be a SQL query
tools = [
    {
        "type": "function",
        "function": {
            "name": "ask_database",
            "description": "Use this function to answer user questions about baseball. Input should be a fully formed SQL query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": """
                                SQL query extracting information from the database to answer the user's question.
                                SQL query should be provided as text, not JSON. Use the following database design.

Here are some sample correct queries in the format user (input, query)

("what players who played at Stanford were inducted into the hall of fame?","SELECT DISTINCT p.nameFirst, p.nameLast, h.yearID FROM People p JOIN HallofFame h ON p.playerID = h.playerID JOIN CollegePlaying c ON p.playerID = c.playerID JOIN Schools s ON c.schoolID = s.schoolID WHERE s.schoolID= 'stanford' AND h.inducted = 'Y'")
("who are the all time Blue Jay home run leaders, and how many homers did they hit?", "SELECT people.nameFirst, people.nameLast, SUM(batting.HR) as homeRuns FROM batting JOIN people ON batting.playerID = people.playerID WHERE batting.teamID = 'TOR' GROUP BY people.playerID ORDER BY homeRuns DESC LIMIT 5;")    
("how many home runs did Reggie Jackson hit between 1975 and 1985?", "SELECT SUM(HR) as total_home_runs FROM Batting WHERE yearID BETWEEN 1975 AND 1985 AND playerID = (SELECT playerID FROM People WHERE nameFirst = 'Reggie' AND nameLast = 'Jackson')")
("who are the top 5 all time leading Saves leaders for the Yankees?", "SELECT People.nameFirst, People.nameLast, SUM(Pitching.SV) as saves FROM Pitching JOIN People ON Pitching.playerID = People.playerID WHERE Pitching.teamID = 'NYA' GROUP BY People.playerID ORDER BY saves DESC LIMIT 5;")
("what major league players played at Cornell University in College?","SELECT DISTINCT p.nameFirst, p.nameLast FROM People p JOIN CollegePlaying c ON p.playerID = c.playerID JOIN Schools s ON c.schoolID = s.schoolID WHERE s.name_full= 'Cornell University';")
("where did Sandy Koufax play College baseball?","SELECT s.name_full FROM Schools s JOIN CollegePlaying c ON s.schoolID = c.schoolID JOIN People p ON c.playerID = p.playerID WHERE p.nameFirst = 'Sandy' AND p.nameLast = 'Koufax';")
("what major league players were born in Canada?", "SELECT * FROM People WHERE birthCountry= 'CAN'")
("who won the most golden glove awards (the top 10)?", "SELECT People.nameFirst, People.nameLast, COUNT(AwardsPlayers.awardID) as gold_glove_count FROM AwardsPlayers JOIN People ON AwardsPlayers.playerID = People.playerID WHERE AwardsPlayers.awardID = 'Gold Glove' GROUP BY People.playerID ORDER BY gold_glove_count DESC LIMIT 10;")
("what Blue Jay players won the most gold gloves. Include only years when they played for the Blue Jays.","SELECT People.nameFirst, People.nameLast, COUNT(AwardsPlayers.awardID) as gold_glove_count FROM AwardsPlayers JOIN People ON AwardsPlayers.playerID = People.playerID JOIN Appearances ON Appearances.playerID = People.playerID WHERE AwardsPlayers.awardID = 'Gold Glove' AND Appearances.teamID = 'TOR' AND AwardsPlayers.yearID = Appearances.yearID GROUP BY People.playerID ORDER BY gold_glove_count DESC;")
("Who are the only two players to win: a.) League MVP b.) World Series MVP and c.) All-Star Game MVP?", "SELECT DISTINCT p.nameFirst, p.nameLast FROM AwardsPlayers a JOIN People p ON a.playerID = p.playerID WHERE a.awardID = 'All-Star Game MVP' AND EXISTS (SELECT 1 FROM AwardsPlayers WHERE awardID = 'World Series MVP' AND playerID = a.playerID) AND EXISTS (SELECT 1 FROM AwardsPlayers WHERE awardID = 'Most Valuable Player' AND playerID = a.playerID);")
("Of the batters with more than 600 career home runs, who never won an MVP award?", "SELECT People.nameFirst, People.nameLast FROM (SELECT playerID FROM Batting GROUP BY playerID HAVING SUM(HR) > 600) AS HRLeaders LEFT JOIN (SELECT DISTINCT playerID FROM AwardsPlayers WHERE awardID = 'Most Valuable Player') AS MVPWinners ON HRLeaders.playerID = MVPWinners.playerID JOIN People ON HRLeaders.playerID = People.playerID WHERE MVPWinners.playerID IS NULL;")
("in what seasons did teams have 4 or more 20-game winning pitchers? Who were the teams?","SELECT Teams.name, Teams.yearID, COUNT(Pitching.W) as twenty_game_winners FROM Pitching JOIN Teams ON Pitching.teamID = Teams.teamID AND Pitching.yearID = Teams.yearID WHERE Pitching.W >= 20 GROUP BY Teams.teamID, Teams.yearID HAVING twenty_game_winners >= 4;)
("Which World Series MVPs started the season playing for a different team than the one with which they won the MVP award?","SELECT DISTINCT p.nameFirst, p.nameLast, a.yearID FROM AwardsPlayers a JOIN People p ON a.playerID = p.playerID JOIN (SELECT playerID, yearID FROM Appearances GROUP BY playerID, yearID HAVING COUNT(DISTINCT teamID) > 1) multi_team_players ON a.playerID = multi_team_players.playerID AND a.yearID = multi_team_players.yearID WHERE a.awardID = 'World Series MVP';")
("What players played in the postseason in the 1950s, 1960s, and 1970s?","SELECT DISTINCT p.nameFirst, p.nameLast FROM People p JOIN BattingPost b ON p.playerID = b.playerID WHERE b.yearID BETWEEN 1950 AND 1979 GROUP BY p.playerID HAVING COUNT(DISTINCT CASE WHEN b.yearID BETWEEN 1950 AND 1959 THEN 1 END) > 0 AND COUNT(DISTINCT CASE WHEN b.yearID BETWEEN 1960 AND 1969 THEN 1 END) > 0 AND COUNT(DISTINCT CASE WHEN b.yearID BETWEEN 1970 AND 1979 THEN 1 END) > 0;") 
("What seasons did Roger Clemens win the Cy Young?","SELECT People.nameFirst, People.nameLast, AwardsPlayers.yearID, AwardsPlayers.awardID FROM AwardsPlayers JOIN People ON AwardsPlayers.playerID = People.playerID WHERE People.nameFirst = 'Roger' AND People.nameLast = 'Clemens' AND AwardsPlayers.awardID = 'Cy Young Award';")
("what seasons did Roger Clemens lead the American Leage in strikeouts, and how many strikeouts did he have.","SELECT p.yearID, p.SO FROM Pitching p JOIN (SELECT yearID, MAX(SO) as MaxSO FROM Pitching WHERE lgID = 'AL' GROUP BY yearID) m ON p.yearID = m.yearID AND p.SO = m.MaxSO WHERE p.playerID = (SELECT playerID FROM People WHERE nameFirst = 'Roger' AND nameLast = 'Clemens');")
("what was Rod Carew's batting average in 1982?","SELECT playerID,yearID,SUM(H) * 1.0 / SUM(AB) AS batting_average FROM Batting WHERE playerID = 'carewro01' AND yearID = 1982 GROUP BY playerID, yearID;")
("what was Rod Carew's career batting average? ","SELECT People.nameLast, People.nameFirst, SUM(Batting.H) * 1.0 / SUM(Batting.AB) AS career_batting_average FROM Batting JOIN People ON Batting.playerID = People.playerID WHERE People.nameFirst = 'Rod' AND People.nameLast = 'Carew' GROUP BY People.playerID;")
("what players won the MVP award at least three seasons. For each season they won, give the player names, and their teams. ","SELECT People.nameFirst, People.nameLast, AwardsPlayers.yearID, Batting.teamID FROM AwardsPlayers JOIN People ON AwardsPlayers.playerID = People.playerID JOIN Batting ON AwardsPlayers.playerID = Batting.playerID AND AwardsPlayers.yearID = Batting.yearID WHERE AwardsPlayers.awardID = 'Most Valuable Player' AND AwardsPlayers.playerID IN (SELECT playerID FROM AwardsPlayers WHERE awardID = 'Most Valuable Player' GROUP BY playerID HAVING COUNT(DISTINCT yearID) >= 3) UNION ALL SELECT People.nameFirst, People.nameLast, AwardsPlayers.yearID, Pitching.teamID FROM AwardsPlayers JOIN People ON AwardsPlayers.playerID = People.playerID JOIN Pitching ON AwardsPlayers.playerID = Pitching.playerID AND AwardsPlayers.yearID = Pitching.yearID WHERE AwardsPlayers.awardID = 'Most Valuable Player' AND AwardsPlayers.playerID IN (SELECT playerID FROM AwardsPlayers WHERE awardID = 'Most Valuable Player' GROUP BY playerID HAVING COUNT(DISTINCT yearID) >= 3)")
("What players born in Mexico played in the all star game? GIve their names, city and country of birth and year of birth.", "SELECT DISTINCT p.nameFirst, p.nameLast, p.birthCity, p.birthCountry, p.birthYear FROM People p JOIN AllStarFull a ON p.playerID = a.playerID WHERE p.birthCountry = 'Mexico'")
("How many players had more bases on balls than strikeouts during their careers","SELECT COUNT(*) FROM (SELECT playerID, SUM(BB), SUM(SO) FROM Batting GROUP BY playerID HAVING SUM(BB) > SUM(SO))")
("What players have had more than 1000 RBIs since 1960?","SELECT playerID, SUM(RBI) AS rbi_total FROM Batting WHERE yearID >= 1960 GROUP BY playerID HAVING rbi_total >= 1000 ORDER BY rbi_total DESC")
("what non-pitchers who played at least 100 games (in total) had the highest total salary per hit between 2000 and 2015? Give first and last names, their total number of hits, total salary, and ratio of salary per hit.","SELECT p.nameFirst, p.nameLast, SUM(b.H) as total_hits, SUM(s.salary) as total_salary, SUM(s.salary) / SUM(b.H) as salary_per_hit FROM People p JOIN Batting b ON p.playerID = b.playerID JOIN Salaries s ON b.playerID = s.playerID AND b.yearID = s.yearID WHERE b.yearID BETWEEN 2000 AND 2015 AND b.G >= 100 AND p.playerID NOT IN (SELECT DISTINCT playerID FROM Pitching WHERE yearID BETWEEN 2000 AND 2015) GROUP BY p.playerID ORDER BY salary_per_hit DESC LIMIT 10;")
("what was the primary position played by Garth Iorg?","SELECT Pos FROM Fielding WHERE playerID = (SELECT playerID FROM People WHERE nameFirst = 'Garth' AND nameLast = 'Iorg') GROUP BY Pos ORDER BY SUM(G) DESC LIMIT 1;")
("what player hit the most homers in world series play? List the top 10.","SELECT People.nameFirst, People.nameLast, SUM(BattingPost.HR) as homeRuns FROM BattingPost JOIN People ON BattingPost.playerID = People.playerID WHERE BattingPost.round = 'WS' GROUP BY People.playerID ORDER BY homeRuns DESC LIMIT 10;")
("what 10 players have the most extra-base hits in world series play?","SELECT People.nameFirst, People.nameLast, SUM(BattingPost."2B" + BattingPost."3B" + BattingPost.HR) as extra_base_hits FROM BattingPost JOIN People ON BattingPost.playerID = People.playerID WHERE BattingPost.round = 'WS' GROUP BY People.playerID ORDER BY extra_base_hits DESC LIMIT 10;")

The database design follows these general principles.  Each player is assigned a unique number (playerID).  All of the information relating to that player
is tagged with his playerID.  The playerIDs are linked to names and birthdates in the People table.

The database is comprised of the following main tables:

  People                 Player names and biographical information
  Teams                  Yearly stats and standings 
  TeamsFranchises        Franchise information
  Parks                  List of major league ballparks
  Batting                Batting statistics
  Pitching               Pitching statistics
  Fielding               Fielding statistics
  FieldingOF             Outfield position data for years where LF/CF/RF fielding data is available
  FieldingOFsplit        LF/CF/RF game played splits for all years, including those where LF/CF/RF fielding data is not available
  Appearances            Details on the positions a player appeared at
  Managers               Managerial statistics

It is supplemented by these tables:

  AllStarFull            All-Star appearances
  BattingPost            Post-season batting statistics
  PitchingPost           Post-season pitching statistics
  FieldingPost           Post-season fielding data
  SeriesPost             Post-season series information
  HomeGames              Number of home games played by each team in each ballpark
  ManagersHalf           Split season data for managers
  TeamsHalf              Split season data for teams
  AwardsManagers         Awards won by managers 
  AwardsPlayers          Awards won by players
  AwardsShareManagers    Award voting data for manager awards
  AwardsSharePlayers     Award voting data for player awards
  HallofFame             Hall of Fame voting data
  CollegePlaying         List of players and the colleges they attended (last updated 2014)
  Salaries               Player salary data (last updated 2016)
  Schools                List of colleges that players attended (last updated 2014)

--------------------------------------------------------------------------------------------------------------------------------------------
PEOPLE TABLE


playerID       A unique code assigned to each player.  The playerID links the data in this file with records in the other files.
birthYear      Year player was born
birthMonth     Month player was born
birthDay       Day player was born
birthCountry   Country where player was born
birthState     State where player was born
birthCity      City where player was born
deathYear      Year player died
deathMonth     Month player died
deathDay       Day player died
deathCountry   Country where player died
deathState     State where player died
deathCity      City where player died
nameFirst      Player's first name
nameLast       Player's last name
nameGiven      Player's given name (typically first and middle)
weight         Player's weight in pounds
height         Player's height in inches
bats           Player's batting hand (left, right, or both)         
throws         Player's throwing hand (left or right)
debut          Date that player made first major league appearance
finalGame      Date that player made first major league appearance (includes date of last played game even if still active)
retroID        ID used by Retrosheet
bbrefID        ID used by Baseball Reference website

---------------------------------------------------------------------
TEAMS TABLE

yearID         Year
lgID           League
teamID         Team
franchID       Franchise (links to TeamsFranchise table)
divID          Team's division
Rank           Position in final standings
G              Games played
GHome          Games played at home
W              Wins
L              Losses
DivWin         Division Winner (Y or N)
WCWin          Wild Card Winner (Y or N)
LgWin          League Champion(Y or N)
WSWin          World Series Winner (Y or N)
R              Runs scored
AB             At bats
H              Hits by batters
2B             Doubles
3B             Triples
HR             Homeruns by batters
BB             Walks by batters
SO             Strikeouts by batters
SB             Stolen bases
CS             Caught stealing
HBP            Batters hit by pitch
SF             Sacrifice flies
RA             Opponents runs scored
ER             Earned runs allowed
ERA            Earned run average
CG             Complete games
SHO            Shutouts
SV             Saves
IPOuts         Outs Pitched (innings pitched x 3)
HA             Hits allowed
HRA            Homeruns allowed
BBA            Walks allowed
SOA            Strikeouts by pitchers
E              Errors
DP             Double Plays
FP             Fielding  percentage
name           Team's full name
park           Name of team's home ballpark
attendance     Home attendance total
BPF            Three-year park factor for batters
PPF            Three-year park factor for pitchers
teamIDBR       Team ID used by Baseball Reference website
teamIDlahman45 Team ID used in Lahman database version 4.5
teamIDretro    Team ID used by Retrosheet

--------------------------------------------------------------------------------------------------------------------------------------------
TEAMSFRANCHISES TABLE

franchID       Franchise ID
franchName     Franchise name
active         Whether team is currently active or not (Y or N)
NAassoc        ID of National Association team franchise played as

--------------------------------------------------------------------------------------------------------------------------------------------
PARKS TABLE

parkkey        Ballpark ID code
parkname       Name of ballpark
parkalias      Alternate names of ballpark, separated by semicolon
city           City
state          State 
country        Country

--------------------------------------------------------------------------------------------------------------------------------------------
BATTING TABLE

playerID       Player ID code
yearID         Year
stint          player's stint (order of appearances within a season)
teamID         Team
lgID           League
G              Games
AB             At Bats
R              Runs
H              Hits
2B             Doubles
3B             Triples
HR             Homeruns
RBI            Runs Batted In
SB             Stolen Bases
CS             Caught Stealing
BB             Base on Balls
SO             Strikeouts
IBB            Intentional walks
HBP            Hit by pitch
SH             Sacrifice hits
SF             Sacrifice flies
GIDP           Grounded into double plays

--------------------------------------------------------------------------------------------------------------------------------------------
PITCHING TABLE

playerID       Player ID code
yearID         Year
stint          player's stint (order of appearances within a season)
teamID         Team
lgID           League
W              Wins
L              Losses
G              Games
GS             Games Started
CG             Complete Games 
SHO            Shutouts
SV             Saves
IPOuts         Outs Pitched (innings pitched x 3)
H              Hits
ER             Earned Runs
HR             Homeruns
BB             Walks
SO             Strikeouts
BAOpp          Opponent's Batting Average
ERA            Earned Run Average
IBB            Intentional Walks
WP             Wild Pitches
HBP            Batters Hit By Pitch
BK             Balks
BFP            Batters faced by Pitcher
GF             Games Finished
R              Runs Allowed
SH             Sacrifices by opposing batters
SF             Sacrifice flies by opposing batters
GIDP           Grounded into double plays by opposing batter

--------------------------------------------------------------------------------------------------------------------------------------------
FIELDING TABLE

playerID       Player ID code
yearID         Year
stint          player's stint (order of appearances within a season)
teamID         Team
lgID           League
Pos            Position
G              Games 
GS             Games Started
InnOuts        Time played in the field expressed as outs 
PO             Putouts
A              Assists
E              Errors
DP             Double Plays
PB             Passed Balls (by catchers)
WP             Wild Pitches (by catchers)
SB             Opponent Stolen Bases (by catchers)
CS             Opponents Caught Stealing (by catchers)
ZR             Zone Rating

--------------------------------------------------------------------------------------------------------------------------------------------
FIELDINGOF TABLE

playerID       Player ID code
yearID         Year
stint          Player's stint (order of appearances within a season)
Glf            Games played in left field
Gcf            Games played in center field
Grf            Games played in right field

--------------------------------------------------------------------------------------------------------------------------------------------
FIELDINGOFSPLIT TABLE

playerID       Player ID code
yearID         Year
stint          Player's stint (order of appearances within a season)
teamID         Team
lgID           League
Pos            Position
G              Games 
GS             Games Started
InnOuts        Time played in the field expressed as outs 
PO             Putouts
A              Assists
E              Errors
DP             Double Plays

--------------------------------------------------------------------------------------------------------------------------------------------
APPEARANCES TABLE

yearID         Year
teamID         Team
lgID           League
playerID       Player ID code
G_all          Total games played
GS             Games started
G_batting      Games in which player batted
G_defense      Games in which player appeared on defense
G_p            Games as pitcher
G_c            Games as catcher
G_1b           Games as first baseman
G_2b           Games as second baseman
G_3b           Games as third baseman
G_ss           Games as shortstop
G_lf           Games as left fielder
G_cf           Games as center fielder
G_rf           Games as right fielder
G_of           Games as outfielder
G_dh           Games as designated hitter
G_ph           Games as pinch hitter
G_pr           Games as pinch runner

--------------------------------------------------------------------------------------------------------------------------------------------
MANAGERS TABLE
 
playerID       Player ID Number
yearID         Year
teamID         Team
lgID           League
inseason       Managerial order, in order of appearance during the year.  One if the individual managed the team the entire year. 
G              Games managed
W              Wins
L              Losses
rank           Team's final position in standings that year
plyrMgr        Player Manager (denoted by 'Y')

--------------------------------------------------------------------------------------------------------------------------------------------
ALLSTARFULL TABLE

playerID       Player ID code
YearID         Year
gameNum        Game number (zero if only one All-Star game played that season)
gameID         Retrosheet ID for the game idea
teamID         Team
lgID           League
GP             1 if Played in the game
startingPos    If player was game starter, the position played

--------------------------------------------------------------------------------------------------------------------------------------------
BATTINGPOST TABLE

yearID         Year
round          Level of playoffs 
playerID       Player ID code
teamID         Team
lgID           League
G              Games
AB             At Bats
R              Runs
H              Hits
2B             Doubles
3B             Triples
HR             Homeruns
RBI            Runs Batted In
SB             Stolen Bases
CS             Caught stealing
BB             Base on Balls
SO             Strikeouts
IBB            Intentional walks
HBP            Hit by pitch
SH             Sacrifices
SF             Sacrifice flies
GIDP           Grounded into double plays

--------------------------------------------------------------------------------------------------------------------------------------------
PITCHINGPOST TABLE

playerID       Player ID code
yearID         Year
round          Level of playoffs 
teamID         Team
lgID           League
W              Wins
L              Losses
G              Games
GS             Games Started
CG             Complete Games
SHO            Shutouts 
SV             Saves
IPOuts         Outs Pitched (innings pitched x 3)
H              Hits
ER             Earned Runs
HR             Homeruns
BB             Walks
SO             Strikeouts
BAOpp          Opponents' batting average
ERA            Earned Run Average
IBB            Intentional Walks
WP             Wild Pitches
HBP            Batters Hit By Pitch
BK             Balks
BFP            Batters faced by Pitcher
GF             Games Finished
R              Runs Allowed
SH             Sacrifice Hits allowed
SF             Sacrifice Flies allowed
GIDP           Grounded into Double Plays

--------------------------------------------------------------------------------------------------------------------------------------------
FIELDINGPOST TABLE

playerID       Player ID code
yearID         Year
teamID         Team
lgID           League
round          Level of playoffs 
Pos            Position
G              Games 
GS             Games Started
InnOuts        Time played in the field expressed as outs 
PO             Putouts
A              Assists
E              Errors
DP             Double Plays
TP             Triple Plays
PB             Passed Balls
SB             Stolen Bases allowed (by catcher)
CS             Caught Stealing (by catcher)

--------------------------------------------------------------------------------------------------------------------------------------------
SERIESPOST TABLE

yearID         Year
round          Level of playoffs 
teamIDwinner   Team ID of the team that won the series
lgIDwinner     League ID of the team that won the series
teamIDloser    Team ID of the team that lost the series
lgIDloser      League ID of the team that lost the series 
wins           Wins by team that won the series
losses         Losses by team that won the series
ties           Tie games

--------------------------------------------------------------------------------------------------------------------------------------------
HOMEGAMES TABLE

yearkey        Year
leaguekey      League
teamkey        Team ID
parkkey        Ballpark ID
spanfirst      Date of first game played
spanlast       Date of last game played
games          Total number of games
openings       Total number of paid dates played (games with attendance)
attendance     Total attendance

--------------------------------------------------------------------------------------------------------------------------------------------
MANAGERSHALF TABLE

playerID       Manager ID code
yearID         Year
teamID         Team
lgID           League
inseason       Managerial order, in order of appearance during the year.  One if the individual managed the team the entire year. 
half           First or second half of season
G              Games managed
W              Wins
L              Losses
rank           Team's position in standings for the half

--------------------------------------------------------------------------------------------------------------------------------------------
TEAMSHALF TABLE

yearID         Year
lgID           League
teamID         Team
half           First or second half of season
divID          Division
DivWin         Won Division (Y or N)
rank           Team's position in standings for the half
G              Games played
W              Wins
L              Losses

--------------------------------------------------------------------------------------------------------------------------------------------
AWARDSMANAGERS TABLE

playerID       Manager ID code
awardID        Name of award won
yearID         Year
lgID           League
tie            Award was a tie (Y or N)
notes          Notes about the award

--------------------------------------------------------------------------------------------------------------------------------------------
AWARDSPLAYERS TABLE

playerID       Player ID code
awardID        Name of award won
yearID         Year
lgID           League
tie            Award was a tie (Y or N)
notes          Notes about the award

--------------------------------------------------------------------------------------------------------------------------------------------
AWARDSSHAREMANAGERS TABLE

awardID        Name of award votes were received for
yearID         Year
lgID           League
playerID       Manager ID code
pointsWon      Number of points received
pointsMax      Maximum number of points possible
votesFirst     Number of first place votes

--------------------------------------------------------------------------------------------------------------------------------------------
AWARDSSHAREPLAYERS TABLE

awardID        Name of award votes were received for
yearID         Year
lgID           League
playerID       Player ID code
pointsWon      Number of points received
pointsMax      Maximum number of points possible
votesFirst     Number of first place votes

--------------------------------------------------------------------------------------------------------------------------------------------
HALLOFFAME TABLE

playerID       Player ID code
yearID         Year of ballot
votedBy        Method by which player was voted upon
ballots        Total ballots cast in that year
needed         Number of votes needed for selection in that year
votes          Total votes received
inducted       Whether player was inducted by that vote or not (Y or N)
category       Category in which candidate was honored
needed_note    Explanation of qualifiers for special elections, revised in 2023 to include important notes about the record.

--------------------------------------------------------------------------------------------------------------------------------------------
COLLEGEPLAYING TABLE

playerid       Player ID code
schoolID       School ID code
year           Year

--------------------------------------------------------------------------------------------------------------------------------------------
SALARIES TABLE

yearID         Year
teamID         Team
lgID           League
playerID       Player ID code
salary         Salary

--------------------------------------------------------------------------------------------------------------------------------------------
SCHOOLS TABLE

schoolID       School ID code
schoolName     School name
schoolCity     City where school is located
schoolState    State where school's city is located
schoolNick     Nickname for school's baseball team

                                """,
                    }
                },
                "required": ["query"],
            },
        }
    }
]

st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True
)

st.title("Baseball Database Chatbot")

st.markdown("I'm a chatbot that has access to the History of Baseball database. \
            This is a comprehensive database that contains tables about teams, players, and their stats between 1871 and the present day.\
            Ask me a question in precise English, and I'll use OpenAI's gpt-4o-mini model to create a database query and query the database to try to answer your question. \
            As an example, you could ask: How many homers did Reggie Jackson hit while he was a member of the New York Yankees? \
            Note that this is different from asking ChatGPT a question and hoping that ChatGPT knows the answer based on its training. \
            Instead, I use AI to try to translate your question into a SQL query, and I use that to look inside a database to get the answer.")

if "messages" not in st.session_state:
    st.session_state.messages = []    

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])  
        
if question := st.chat_input("Ask your question about Baseball History."):

    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    response_message = ask_question_openai(question,tools,client)
        
    with st.chat_message("assistant"):
        tool_calls = response_message.tool_calls
 
        if tool_calls:
            # If true the model will return the name of the tool / function to call and the argument(s)  
            tool_call_id = tool_calls[-1].id
            tool_function_name = tool_calls[-1].function.name
            tool_query_string = json.loads(tool_calls[-1].function.arguments)['query']
            st.markdown(tool_query_string)
            
            if tool_function_name == 'ask_database':
                response = ask_database(conn, tool_query_string)
                st.write(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
        else:
            st.markdown("I'm not able to come up with a good database query using your question. Please try again.")
             



    