#
# all bauble exceptions and errors
#


# TODO: should I make everything extend from BaubleException

class CommitException(Exception):

    def __init__(self, exc, row):
        self.row = row # the model we were trying to commit
        self.exc = exc # the exception thrown while committing
    
    def __str__(self):
        return str(self.exc)