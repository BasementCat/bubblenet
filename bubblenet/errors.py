class Error(Exception):
    pass


class AddressError(Error):
    pass


class AddressParseError(AddressError):
    pass


class EndpointError(Error):
    pass


class EndpointParseError(EndpointError):
    pass
