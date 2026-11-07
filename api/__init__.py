from dotenv import load_dotenv

# The shared postgres package reads POSTGRES_* from os.environ when it is first
# imported, so .env has to be loaded before any api module imports it.
load_dotenv()
