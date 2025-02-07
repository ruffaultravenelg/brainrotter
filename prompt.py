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
PROMPT = os.getenv("MODEL_PROMPT")
MODEL = os.getenv("MODEL")

# Configure API
genai.configure(api_key=GOOGLE_API_KEY)

# Get model
model = genai.GenerativeModel(MODEL)

# Create the prompt for gemini
def generateGeminiPrompt(userPrompt):
    return PROMPT.replace(r"{{prompt}}", '"' + userPrompt.strip() + '"')

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