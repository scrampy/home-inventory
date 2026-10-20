from dotenv import load_dotenv

load_dotenv()

from homeinv import create_app  # noqa: E402

app = create_app()
