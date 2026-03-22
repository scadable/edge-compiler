from abc import ABC, abstractmethod

class Protocol(ABC):
    @abstractmethod
    def read(self, *args, **kwargs):
        pass

    @abstractmethod
    def write(self, *args, **kwargs):
        pass
