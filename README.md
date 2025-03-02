# Baseball_SQL_Chatbot

This is a Streamlit application that uses an LLM to generate SQL statements that answer a text question entered by a user regarding baseball statistics, and executes that statement against the Lahman baseball database (http://seanlahman.com/). I took the various tables in the database, loaded them into SQLite and stored the resulting database in a director called /data, below the main directory.

In this Chatbot, I don't store the whole context of your conversation, so if the bot doesn't know how to generate SQL that answers your question, or the SQL results in a database error when executed, try again and change the wording of your question.

You need to get an OpenAI API token and insert it into the code where indicated. 

I borrowed the code to force OpenAI to generate a SQL call from the OpenAI cookbook:
https://github.com/openai/openai-cookbook/blob/main/examples/How_to_call_functions_with_chat_models.ipynb


