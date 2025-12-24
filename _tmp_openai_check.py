import os
print({'OPENAI_API_KEY': bool(os.getenv('OPENAI_API_KEY'))})
from utils.ai_.module import is_openai_configured
print({'is_openai_configured': is_openai_configured()})
