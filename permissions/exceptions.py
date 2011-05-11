class Unauthorized(Exception):
    def __init__(self, str):
        super(Unauthorized, self).__init__(str)