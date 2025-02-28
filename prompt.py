# Imports
from dotenv import load_dotenv
import pathlib
import os
import textwrap
import google.generativeai as genai

# Load environment
load_dotenv()

# Load google api
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
PROMPT_FILE = os.path.join(os.path.dirname(__file__), os.getenv("PROMPT_FILE"))
MODEL = os.getenv("MODEL")

# Read prompt from file
with open(PROMPT_FILE, 'r', encoding='utf-8') as file:
    PROMPT = file.read().strip()

# Configure API
genai.configure(api_key=GOOGLE_API_KEY)

# Get model
model = genai.GenerativeModel(MODEL)

# Create the prompt for gemini
def generateGeminiPrompt(userPrompt):
    return PROMPT.replace(r"{{prompt}}", userPrompt.strip())

# Generate script
def generateScriptFromPrompt(userPrompt):
    """
    Generate a script from the given prompt.
    """
    # Generate script
    prompt = generateGeminiPrompt(userPrompt)
    response = model.generate_content(prompt)
    script = response.text

    # Return script
    return script