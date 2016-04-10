import re

INTEGER_PROPERTIES = set(['limit', 'skip'])
STRING_PROPERTIES = set([])
ORDER_BY_PROPERTIES = set(['order_by'])
CONSTRAINT_PROPERTIES = set(['where'])
INCLUDE_PROPERTIES = set(['include'])

def get_query_dict_from_params(params):
    include_param = params.get('include', None)
    constraint_param = params.get('where', None)
    skip_param = params.get('skip', None)
    order_by_param = params.get('order_by', None)
    limit_param = params.get('limit', 100)

    query_dict = {}
    if include_param:
        query_dict['include'] = ParamParser.parse_include_list(include_param)

    if constraint_param:
        query_dict['where'] = ParamParser.parse_constraint_list(constraint_param)

    if order_by_param:
        query_dict['order_by'] = skip_value

    if skip_param:
        try:
            skip_value = int(skip_param)
        except ValueError:
            raise ParamParsingException("Non integer value '" + skip_param + "' for an integer property.")
        query_dict['skip'] = skip_value


    if limit_param:
        try:
            limit_value = int(limit_param)
        except ValueError:
            raise ParamParsingException("Non integer value '" + skip_param + "' for an integer property.")
        query_dict['limit'] = limit_value

    return query_dict


class ParamParsingException(Exception):
    pass


class ParamParser(object):
    """
    A class designed to provide tools for parsing the url parameters of the
    graph API according to the rules of the API grammar.
    """

    @staticmethod
    def split_on_char_outside_pair(char, pair, string):
        # Split on periods where they are followed by some number of
        # characters which are not a closing bracket and then an opening
        # bracket or the end of the line. It is impossible to tell if a period
        # is inside or outside of parentheses with a regular language. Thus the
        # stack.
        stack = 0
        indices = [-1]
        for i, c in enumerate(string):
            if c == pair[0]:
                stack += 1
            elif c == pair[1]:
                if stack > 0:
                    stack -= 1
                else:
                    raise ParamParsingException("Unmatched '" + pair[1] + "'.")
            elif c == char and stack == 0:
                indices.append(i)
        if stack > 0:
            raise ParamParsingException("Unmatched '" + pair[0] + "'.")

        a = []
        for i, index in enumerate(indices):
            if i < len(indices) - 1:
                a.append(string[index + 1:indices[i + 1]])
            else:
                a.append(string[index + 1:])
        return a

    @staticmethod
    def parse_property(property_string):
        name = property_string.partition('(')[0]
        value = property_string[:-1].partition('(')[-1]
        property_dict = {}
        if not value:
            raise ParamParsingException()  #All properties must have a value
        if name in INTEGER_PROPERTIES:
            try:
                value = int(value)
            except ValueError:
                raise ParamParsingException("Non integer value '" + value + "' for an integer property.")
        elif name in CONSTRAINT_PROPERTIES:
            value = ParamParser.parse_constraint_list(value)
        elif name in STRING_PROPERTIES:
            if not isinstance(value, basestring):
                raise ParamParsingException("{} property must be a string".format(name))
        elif name in ORDER_BY_PROPERTIES:
            value = ParamParser.parse_order_by_params(value)
        elif name in INCLUDE_PROPERTIES:
            value = ParamParser.parse_include_list(value)
        else:
            raise ParamParsingException("Unrecognized property.")
        return name, value

    @staticmethod
    def parse_order_by_params(params_string):
        params = ParamParser.split_on_char_outside_pair(",", ("(", ")"), params_string)

        if not params:
            raise ParamParsingException("Order by must specify a key for ordering.")

        if not isinstance(params[0], basestring):
            raise ParamParsingException("The order by key must be a string")

        direction = "asc"
        if len(params) > 1:
            if params[1] == "desc":
                direction = "desc"
            elif params[1] == "asc":
                direction = "asc"
            else:
                raise ParamParsingException(
                    "The optional second argument to order by must be either 'asc' or 'desc'."
                )
        return (params[0], direction)

    @staticmethod
    def parse_include_list(field_list_string):
        fields = ParamParser.split_on_char_outside_pair(",", ("(", ")"), field_list_string)
        field_dict = {}
        for field_string in fields:
            properties = ParamParser.split_on_char_outside_pair(".", ("(", ")"), field_string)
            field_name = properties[0]
            properties = properties[1:]
            if properties:
                property_dict = {}
                for p in properties:
                    name, value = ParamParser.parse_property(p)
                    if name in property_dict:
                        raise ParamParsingException("You can't specify the same property twice")
                    property_dict[name] = value
                field_dict[field_name] = property_dict
            else:
                field_dict[field_name] = None
        return field_dict

    @staticmethod
    def parse_constraint_list(constraint_list_string):
        # Constraints should not be nested, but may be functions with comma
        # separated arguments.
        valid_comparison_operators = set(['!=', '=', '<=', '>=', '<', '>', 'matches'])
        valid_logical_operators = set(['|', ','])
        or_clauses = ParamParser.split_on_char_outside_pair("|", ("(", ")"), constraint_list_string)
        or_constraints = []
        for or_clause in or_clauses:
            and_expressions = ParamParser.split_on_char_outside_pair(",", ("(", ")"), or_clause)
            and_constraints = []
            for expression in and_expressions:
                if 'matches' in expression:
                    attribute = expression.split('.')[0]
                    operator = 'matches'
                    value = expression.partition('(')[2][:-1]
                else:
                    matching_operators = filter(lambda o: o in expression, valid_comparison_operators)
                    if not matching_operators:
                        raise ParamParsingException("There is no comparision operator in the expression '{}'.".format(
                            expression))
                    expression_operator = max(matching_operators, key=len)
                    attribute, operator, value = expression.partition(expression_operator)
                and_constraints.append((attribute, operator, value))
            or_constraints.append(and_constraints)
        return or_constraints


if __name__ == '__main__':
    import json
    test1 = 'hungryFriends.limit(10)'
    test2 = 'friendRequests,friends.where(name=Tyler,email.matches(*@aol.com)|name=Kyle).limit(2).skip(3).include(updateEvents,friends.include(friends,updateEvents)),updateEvents'
    test3 = 'friends.limit(8).skip(5).where(name=Tyler)'
    print json.dumps(ParamParser.parse_include_list(test1), sort_keys=True, indent=4)
    print json.dumps(ParamParser.parse_include_list(test2), sort_keys=True, indent=4)
    print json.dumps(ParamParser.parse_include_list(test3), sort_keys=True, indent=4)
