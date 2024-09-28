from dotenv import load_dotenv
import chainlit as cl
import json
from movie_functions import get_now_playing_movies, get_reviews, get_showtimes, buy_ticket
from prompt import SYSTEM_PROMPT

load_dotenv()

# Note: If switching to LangSmith, uncomment the following, and replace @observe with @traceable
# from langsmith.wrappers import wrap_openai
# from langsmith import traceable
# client = wrap_openai(openai.AsyncClient())

from langfuse.decorators import observe
from langfuse.openai import AsyncOpenAI
 
client = AsyncOpenAI()

gen_kwargs = {
    "model": "gpt-4o",
    "temperature": 0.2,
    "max_tokens": 500
}

SYSTEM_PROMPT = SYSTEM_PROMPT

@observe
@cl.on_chat_start
def on_chat_start():    
    message_history = [{"role": "system", "content": SYSTEM_PROMPT}]
    cl.user_session.set("message_history", message_history)

@observe
async def generate_response(client, message_history, gen_kwargs):
    response_message = cl.Message(content="")
    await response_message.send()

    stream = await client.chat.completions.create(messages=message_history, stream=True, **gen_kwargs)
    async for part in stream:
        if token := part.choices[0].delta.content or "":
            await response_message.stream_token(token)
    
    await response_message.update()

    return response_message

def function_call(response):
        function_call = response["function"]
        if function_call == "get_now_playing_movies":
            fc_response = get_now_playing_movies()

        elif function_call == "get_reviews":
            movie_id = response["movie_id"]
            fc_response = get_reviews(movie_id=movie_id)

        elif function_call == "get_showtimes":
            title = response["title"]
            location =  response["location"]
            fc_response = get_showtimes(title=title,location=location)

        elif function_call == "buy_ticket":
            theater = response["theater"]
            movie =  response["movie"]
            showtime = response["showtime"]
            fc_response = buy_ticket(theater=theater,movie=movie, showtime=showtime)
     
        return fc_response

@cl.on_message
@observe
async def on_message(message: cl.Message):
    message_history = cl.user_session.get("message_history", [])
    message_history.append({"role": "user", "content": message.content})   
    response_message = await generate_response(client, message_history, gen_kwargs)
    try:
        response = json.loads(response_message.content)
        if response["function"]:
            fc_response = function_call(response)
            message_history.append({"role": "system", "content": fc_response})  
            response_message = await generate_response(client, message_history, gen_kwargs)
        else:
            message_history.append({"role": "system", "content": response_message.content})  
            response_message = await generate_response(client, message_history, gen_kwargs)
    except json.JSONDecodeError as e:
        print(e.msg)
    
    message_history.append({"role": "assistant", "content": response_message.content}) 
    for m in message_history:
            if m.get('role') == 'assistant' and "function" in (m.get("content")):
                dict_str = m.get("content").split(".")[-1]
                try:
                    response = json.loads(dict_str)
                    fc_response = function_call(response)
                    message_history.append({"role": "system", "content": fc_response})  
                    response_message = await generate_response(client, message_history, gen_kwargs)
                except json.JSONDecodeError as e:
                        print(e.msg)

                       
        

    
    cl.user_session.set("message_history", message_history)

if __name__ == "__main__":
    cl.main()
