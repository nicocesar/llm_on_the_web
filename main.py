#!/usr/bin/env python3
import asyncio
from pyppeteer import launch
from openai import OpenAI
import json

async def webAsync(url, javascript_commands):
    browser = await launch(headless=True)
    page = await browser.newPage()
    await page.goto(url)
    return_array=[]
    for javascript_string in javascript_commands:
        try: 
            result = await page.evaluate("() => ( %s )" % javascript_string)
        except Exception as e:
            result = str(e)
        return_array.append(result)
    await browser.close()    
    return return_array

def web(url, javascript_commands):
    print("calling the web...", url, javascript_commands)
    r = asyncio.get_event_loop().run_until_complete(
        webAsync(url, javascript_commands)
    )
    print("returning from the web...", r)
    return r


client = OpenAI()

def run_conversation(question):
    # Step 1: send the conversation and available functions to the model
    messages = [{"role": "user", "content": question }]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "web",
                "description": "Get the execution of javascript on a headless webBrowser",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The URL to visit",
                        },
                        "javascript_commands": {
                            "type": "array",
                            "description": "Array of javascript commands to execute. Each command should be a string and return a value without the use of const",
                            "items": {"type": "string"}
                        },
                    },
                    "required": ["url", "javascript_commands"],
                }
            }
        }
    ]
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        tools=tools,
        tool_choice="auto",  # auto is default, but we'll be explicit
    )
    response_message = response.choices[0].message
    tool_calls = response_message.tool_calls
    # Step 2: check if the model wanted to call a function
    if tool_calls:
        # Step 3: call the function
        # Note: the JSON response may not always be valid; be sure to handle errors
        available_functions = {
            "web": web,
        }  # only one function in this example, but you can have multiple
        messages.append(response_message)  # extend conversation with assistant's reply
        # Step 4: send the info for each function call and function response to the model
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            function_to_call = available_functions[function_name]
            function_args = json.loads(tool_call.function.arguments)
            function_response = function_to_call(
                url=function_args.get("url"),
                javascript_commands=function_args.get("javascript_commands"),
            )
            messages.append(
                {
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": json.dumps(function_response),
                }
            )  # extend conversation with function response
        second_response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
        )  # get a new response from the model where it can see the function response
        return second_response


import argparse

parser = argparse.ArgumentParser(description="Ask a question or task to an agent that has access to Javascript console in a headless browser .")
parser.add_argument('question', type=str, help='Question or task for an agent', nargs='+')
args = parser.parse_args()
question = ' '.join(args.question)

print(run_conversation(question).choices[0].message.content)

