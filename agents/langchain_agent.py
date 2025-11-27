import os

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import ResponseSchema, StructuredOutputParser

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
    api_key=os.getenv("OPENAI_API_KEY", "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")
)

# Define schema for parsing user messages
response_schemas = [
    ResponseSchema(name="intent", description="Intent type, e.g., add_expense, delete_expense, "
                                              "expenses_history, expense_summary, debt_summary, credit_summary, "
                                              "confirmation"),
    ResponseSchema(name="payer", description="Name of person who paid"),
    ResponseSchema(name="title", description="Title of the expense"),
    ResponseSchema(name="amount", description="Numeric amount paid"),
    ResponseSchema(name="participants", description="Comma-separated participant names"),
    ResponseSchema(name="split", description="List of tuple each with participant name and his split in the amount"),
    ResponseSchema(name="split_type", description="Split type of the expense. It should be either "
                                                  "amount, ratio or percentage.")
]

output_parser = StructuredOutputParser.from_response_schemas(response_schemas)

prompt_template = ChatPromptTemplate.from_template("""
You are a smart assistant for a group expense tracker.

Extract the following fields from the user's message:
- intent (e.g., add_expense, update_expense, delete_expense, debt_summary, credit_summary)
- payer (the person who paid)
- amount (numeric amount paid)
- participants (comma-separated names of all participants, including payer if applicable)
- split (list of JSON objects; each object must have participant and share fields)
- split_type (the type of split; must be amount, ratio, or percentage)

CRITICAL RULES:
1. Your response MUST be valid JSON — not Markdown, not natural language.
2. Whichever data you can't extract, send NA for that field if it is string. If numeric then send 0. 
If list then empty list.

Message: {message}

{format_instructions}
""")


def interpret_message(message: str):
    prompt = prompt_template.format_messages(
        message=message,
        format_instructions=output_parser.get_format_instructions()
    )
    response = llm(prompt)
    return output_parser.parse(response.content)
