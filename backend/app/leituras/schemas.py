from pydantic import BaseModel

class LeituraIn(BaseModel):
    codigo: str
    ppm:float