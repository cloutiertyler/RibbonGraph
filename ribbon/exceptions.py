from rest_framework.exceptions import APIException
from rest_framework import status


class GraphAPIError(APIException):
    """Base class for exceptions in this module."""
    pass


class NodeNotFoundError(GraphAPIError):
    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, id):
        self.id = id
        super(NodeNotFoundError, self).__init__("Node with id '{}' does not exist.".format(id))


class NodeTypeNotFoundError(GraphAPIError):
    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, node_type):
        self.node_type = node_type
        super(NodeTypeNotFoundError, self).__init__("Node type '{}' does not exist.".format(node_type))


class MissingNodeTypeError(GraphAPIError):
    """ Creating a node requires a type. """
    status_code = status.HTTP_400_BAD_REQUEST


class MalformedUpdateDictionaryError(GraphAPIError):
    status_code = status.HTTP_400_BAD_REQUEST


class InvalidPropertyError(GraphAPIError):
    status_code = status.HTTP_400_BAD_REQUEST

class InvalidValueError(GraphAPIError):
    status_code = status.HTTP_400_BAD_REQUEST

class PermissionDenied(GraphAPIError):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'Insufficient permissions for the request.'
