# Baseball_SQL_Chatbot

This is a chatbot that uses an LLM to generate SQL statements that answer a text question entered by a user regarding baseball statistics, and executes that statement against the Lahman baseball database (http://seanlahman.com/).

I took the various tables in the database, loaded them into SQLite and stored the resulting database in a .db file.

The chatbot is built using a very simple Streamlit application. I don't store the whole context of your conversation, so if the bot doesn't know how to generate SQL that answers your question, or the SQL results in a database error when executed, try again and change the wording of your question.

OpenAI functions are used to force the LLM's output to meet some fixed criteria--in this case we want to generate SQL that we can execute against the database. You need to get an OpenAI API token and make it available to the app as an environment variable when you fire up the streamlit app on your desktop, or when you fire it up in a container in the cloud.

I borrowed the code to force OpenAI to generate a SQL call from the OpenAI cookbook:
https://github.com/openai/openai-cookbook/blob/main/examples/How_to_call_functions_with_chat_models.ipynb


