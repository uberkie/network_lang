from attr import dataclass


@dataclass
class UsermanRouters:
    name: str
    shared_secret: str
    address: str
    coa_port: int
    