class Symbol:
    instances = {}

    def __new__(cls, name: str):
        name = str(name)
        if name not in cls.instances:
            self = super(Symbol, cls).__new__(cls)
            self.__init__(name)
            cls.instances[name] = self
        return cls.instances[name]

    def __init__(self, name: str):
        self.name   = str(name)
        self.__hash = None

    def __repr__(self):
        return f"Symbol({self.name})"

    def __hash__(self):
        self.__hash = self.__hash or hash(self.name)
        return self.__hash
