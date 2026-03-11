"""
Outparse — configurable fast printout parser.

This module provides the `PrintoutParser` class which converts human-readable
CLI printouts into structured Python data.

Features
--------
- Parses line-wrapped tables
- Supports horizontal key–value parameters
- Supports parent/child hierarchical objects
- Works without external dependencies

Typical usage:

    from outparse import PrintoutParser

    parser = PrintoutParser()
    result = parser.parse(text)

The parser returns a list of dictionaries representing parsed objects.

For full documentation and examples see the project README.
"""


import collections
import logging
import re


ID_PARAM_KEY = 'object_id_param_name'  # name of the key holding object id
COLUMN_SEPARATOR_SPACES_COUNT = 1  # Number of spaces separating columns


class PrintoutParser:

    def __init__(self,
                 object_relations={},
                 object_id_param_names=[],
                 hor_param_names=[],
                 value_delimiters='\\s|,',
                 keep_order=False):

        """
        :param object_relations:
        Defines parent–child relationships between object identifier parameters.
        Format:
            {
                "PARENT_ID": ["CHILD_ID_1", "CHILD_ID_2"],
                ...
            }
        Each key is a parent identifier parameter name.
        Each value is a list of identifier parameter names treated as children
        (including indirect descendants).
        Default: {}.

        :param object_id_param_names:
        List of parameter names that must be treated as object identifiers.
        When provided:
        - Only these parameters can start a new object
        - Section changes will NOT reset identifier detection automatically
        Default: [].

        :param value_delimiters:
        Regular expression used to split parameter values.
        Default: '\\s|,' (split by whitespace or comma).
        Set to None or '' to disable splitting (values stored as single-item lists).

        :param hor_param_names:
        List of horizontal parameter names.
        Horizontal parameters are those whose name and value appear on the same line.
        They are not auto-detected and must be explicitly listed here.
        Default: [].

        :param keep_order:
        If True, preserves parameter insertion order in the result structure
        using OrderedDict (slightly slower).
        If False, uses regular dict for better performance.
        Default: False.
        """

        logging.debug('Call PrintoutParser init')

        # Handling kwargs
        assert type(object_id_param_names) == list
        self._object_id_param_names = object_id_param_names

        assert type(object_relations) == dict
        self._object_relations = object_relations

        self._value_delimiters = value_delimiters

        assert type(hor_param_names) == list
        self._hor_param_names = hor_param_names

        self._keep_order = keep_order

        # ********************************** INSTANCE VARIABLES **********************************
        self._id_param_name = None  # Name of current object identifier

        self._param_parse_map = {}    # Structure for storing parameters parse index boundaries (parse map)

        # parent-child relation model handling
        self._child_ids = []  # List of child ids in printout being analyzed
        self._is_param_child_id = False  # Flag shows if current parameter is child identifier

        self._save_as_list_of_lists = False  # Flag shows if parameter is related to child object, hence, should be saved as list of lists
        self._save_as_list_of_lists_all = {}  # save_as_list_of_lists attribute saved for all parameters

        self._is_new_child_started = False  # Flag shows if new child started

        self._cur_child_id = None  # Child identity saved as (name, value) for current child parameter
        self._param_to_child_id_mapping = {}  # Holds child identity values for each child parameter

        self._child_counts = {}    # Dictionary with child instance counters for each child type in current object

        # Storing results
        self._parsed_param_data = collections.OrderedDict() if self._keep_order else {}  # line parameters buffer dictionary
        self._cur_obj = collections.OrderedDict() if self._keep_order else {}  # Dictionary storing parameters of the object being constructed
        self._result_object_list = []    # Result objects list


    def _split_values_line_to_list(self, value_line):
        """
        This function splits value line to list of tokens, depending on delimiters parser option.
        """

        logging.debug(f'Call _split_values_line_to_list({value_line})')
        logging.debug(f'self._value_delimiters={self._value_delimiters}')

        if self._value_delimiters:
            # Splitting multiple values in a row, separated by delimiters
            param_values_list = re.split(self._value_delimiters, value_line)
        else:
            param_values_list = [value_line]  # If no delimiters specified, parameter values string is taken as single item of its values list

        # Remove all empty strings which occurs in splitlist as a result of custom split character usage
        param_values_list = [p.strip() for p in param_values_list if p]

        logging.debug('Finish _split_values_line_to_list()')

        return param_values_list


    def _is_param_l_justified(self, param_name, param_name_start_pos, param_name_end_pos, right_search_border, text_table_lines, curr_line_number):

        """
        This internal  function checks if parameter value is left justified (normal case) to its header.
        """

        logging.debug(f'Call _is_param_l_justified with {(param_name, param_name_start_pos, param_name_end_pos, right_search_border, '...')}')

        # Flags storing parameter L- or R -justified (default is left justified)

        # for current line
        flag_cur_param_l_justified = None
        flag_cur_param_r_justified = None

        # accumulated attributes
        are_all_vals_l_justified = None
        are_all_vals_r_justified = None

        # Combination of those initial values of isLinePossiblyParamRelated and prev_line will allow first line analysis
        is_line_possibly_param_related = True  # Flag shows that current line related to current parameter's value
        prev_line = None  # saved previous line

        for i in range(curr_line_number, len(text_table_lines)):

            cur_line = text_table_lines[i]
            logging.debug(f'cur_line={cur_line}')

            if prev_line == '':
                # empty previous line means current line is a header line,
                # so recheck whether further vales lines are related to our parameter
                # (they are in case header contains parameter name that we are interested in)

                is_line_possibly_param_related = cur_line[param_name_start_pos:param_name_end_pos] == param_name
                logging.debug(f'Updated is_line_possibly_param_related={is_line_possibly_param_related}')

                prev_line = cur_line  # save previous line for next iteration

                logging.debug(f'prev_line is changed to: {prev_line}')

                continue  # Skip analyzing header line, only values lines are evaluated

            logging.debug(f'is_line_possibly_param_related={is_line_possibly_param_related}')


            if is_line_possibly_param_related and cur_line[param_name_start_pos:right_search_border].strip():  # omit cases with no value, its causing fake statistics
                # Check if parameter value is left justified to its header
                try:
                    flag_cur_param_l_justified = cur_line[param_name_start_pos] != ' '
                    if param_name_start_pos > 0:
                        flag_cur_param_l_justified = flag_cur_param_l_justified and cur_line[param_name_start_pos - 1] == ' '

                    logging.debug(f'flag_cur_param_l_justified={flag_cur_param_l_justified}')

                except IndexError:

                    # current values line is too short and therefore does not contain parameter being analyzed
                    # Switching to next line
                    logging.debug(f'IndexError while checking is_param_l_justified, analyzing next line')
                    prev_line = cur_line  # save previous line for next iteration
                    logging.debug(f'prev_line is changed to: {prev_line}')
                    continue

                # Detect if parameter value is right justified to its header
                try:
                    flag_cur_param_r_justified = cur_line[param_name_end_pos - 1] != ' '
                    try:
                        flag_cur_param_r_justified = flag_cur_param_r_justified and cur_line[param_name_end_pos] == ' '
                    except IndexError:  # Possibly right justified parameter due to right border is end of line
                        logging.debug('IndexError when checking is_param_r_justified, assuming it is possibly right justified due to end of the line')
                except IndexError:
                    # Means corresponding right part is unreachable due to line is too short.
                    # But it's ok since parameter value may be left justified and saved a bit left.
                    # Also means that parameter can't be right justified.
                    flag_cur_param_r_justified = False
                    logging.debug('IndexError when checking is_param_r_justified, so it was set to False')

                logging.debug(f'is_param_r_justified={flag_cur_param_r_justified}')

                # Flags can be valid when they are different
                # but we can trust this method only if left justification detected
                if flag_cur_param_l_justified and not flag_cur_param_r_justified:

                    logging.debug(f'Different justification modes detected, returning {flag_cur_param_l_justified}')
                    return flag_cur_param_l_justified

                # Evaluating common attributes
                if are_all_vals_l_justified == None:
                    are_all_vals_l_justified = flag_cur_param_l_justified
                else:
                    are_all_vals_l_justified = are_all_vals_l_justified and flag_cur_param_l_justified

                logging.debug(f'are_all_vals_l_justified={are_all_vals_l_justified}')

                if are_all_vals_r_justified == None:
                    are_all_vals_r_justified = flag_cur_param_r_justified
                else:
                    are_all_vals_r_justified = are_all_vals_r_justified and flag_cur_param_r_justified

                logging.debug(f'are_all_vals_r_justified={are_all_vals_r_justified}')

            prev_line = cur_line  # save previous line for next iteration

            logging.debug(f'prev_line is changed to: {prev_line}')

        # Basing on its truth table, final result is a reverse implication (A or not B) of accumulated attributes:
        # +--------------------+---------------------+--------+-------------------------------------------------------------------------------------------------+
        # | All left justified | All right justified | Result | Meaning                                                                                         |
        # +--------------------+---------------------+--------+------------------------------------------------------------------------------------------------_+
        # | No                 | No                  | Yes    | Uncertainity - no values or values shifted from its header, assume default justification - left |
        # | No                 | Yes                 | No     | Certainly - right justification                                                                 |
        # | Yes                | No                  | Yes    | Certainly - left justification                                                                  |
        # | Yes                | Yes                 | Yes    | Uncertainity - all values directly under header, assume default justification - left            |
        # +--------------------+---------------------+--------+-------------------------------------------------------------------------------------------------+
        res = are_all_vals_l_justified or not are_all_vals_r_justified
        logging.debug(f'Finish _is_param_l_justified(), returning final result: {res}')
        return res


    def _finalize_object(self):
        """
        This function saves current result object dictionary into final result list.
        """

        logging.debug('Call _finalize_object()')
        logging.debug(f'before self._cur_obj={self._cur_obj}')
        logging.debug(f'before self.__result_object_list={self._result_object_list}')

        if self._cur_obj:
            # if any data collected, save generic keys and append object to result list
            self._cur_obj[ID_PARAM_KEY] = self._id_param_name  # save object id parameter name with fixed key

            self._result_object_list.append(self._cur_obj)  # append object data to result object list

            # Clear data
            self._cur_obj = collections.OrderedDict() if self._keep_order else {}
            self._save_as_list_of_lists = False  # reset attribute for new object
            self._cur_child_id = None
            self._is_new_child_started = False
            self._child_counts = {}
            self._param_to_child_id_mapping = {}    # Holds child identity values for each child parameter

            logging.debug('Object finalized')

        logging.debug(f'after self._cur_obj={self._cur_obj}')
        logging.debug(f'after self.__result_object_list={self._result_object_list}')
        logging.debug(f'_finalize_object() finished')


    def _save_param(self, param_name, param_values, save_as_list_of_lists):
        """
        This function saves given parameter into current result object dictionary.
        """
        logging.debug(f'\nCall _save_param{(param_name, param_values, save_as_list_of_lists)}')
        try:
            # empty (phantom) current child id value or same as saved for child parameter means no new child object
            self._is_new_child_started = (self._cur_child_id
                                          and
                                          self._cur_child_id[1]
                                          and
                                          self._cur_child_id != self._param_to_child_id_mapping[param_name])

            logging.debug(f'Found saved value for self._param_to_child_id_mapping[{param_name}]={self._param_to_child_id_mapping[param_name]}')
            logging.debug(f'self._cur_child_id=={self._cur_child_id}')

        except KeyError:                          # saving child parameter for first time,
            self._is_new_child_started = True     # so saving _param_to_child_id_mapping is required
            logging.debug(f'self._is_new_child_started={self._is_new_child_started} due to no value found: self._param_to_child_id_mapping[{param_name}]')

        logging.debug(f'self._is_new_child_started={self._is_new_child_started}')

        # Saving parameter into current object
        if param_name in self._cur_obj:                # if parameter already in current object

            logging.debug(f'Found self._cur_obj[{param_name}]={self._cur_obj[param_name]}')

            if save_as_list_of_lists:                  # and if this is child object related parameter
                if self._is_new_child_started:         # and if new child object started (if value present in child object id header)

                    logging.debug('Appending list of parameter values to existing list of lists:')
                    logging.debug(f'param_name=={param_name}')
                    logging.debug(f'self._cur_obj=={self._cur_obj}')
                    logging.debug(f'self._cur_child_id=={self._cur_child_id}')
                    logging.debug(f'self._child_counts=={self._child_counts}')

                    # if this parameter is not child object id
                    # (as it causes redundant empty values for second type of child object which treated as nested,
                    # and because redundant child object parameter which is also child object id is incorrect)
                    # if this is not usual parameter, duplicate of child object parameter
                    # (parent child object id exists for the parameter, means self._cur_child_id is not empty)
                    # and this is not phantom occurrence of child object id parameter
                    # (child object id is empty, but subordinate child object parameter exists)
                    if not self._is_param_child_id and self._cur_child_id and self._cur_child_id[1]:
                        for i in range(self._child_counts[self._cur_child_id[0]] - len(self._cur_obj[param_name])):
                            self._cur_obj[param_name].append([])          # add proper amount of empty elements
                                                                          # (used for proper matching child object parameter values to child object ids,
                                                                          # in case of optional child object parameters)
                            logging.debug(f'Added empty element for child object parameter {param_name}')

                    self._cur_obj[param_name].append(param_values)        # add its list of values data as separate item (like list in list)

                    if self._cur_child_id and self._cur_child_id[1]:                      # avoid phantom occurrences of the parameter (with no value)
                        self._param_to_child_id_mapping[param_name] = self._cur_child_id  # save current child id
                        logging.debug(f'Setting self._param_to_child_id_mapping[{param_name}]={self._param_to_child_id_mapping[param_name]}')

                else:
                    logging.debug('extending last element of parameter values list:\n'
                                  f'self._cur_obj[{param_name}]=={self._cur_obj[param_name]}')

                    self._cur_obj[param_name][-1].extend(param_values)  # in case it is the same child object, extend its nested list

            else:                                               # if it is not child object related parameters (plain parameters)
                self._cur_obj[param_name].extend(param_values)  # if this is plain parameter, just add new values to its list of values

        else:    # Saving as new parameter

            logging.debug('saving new parameter into _cur_obj:')

            if save_as_list_of_lists:  # if this is child object parameter

                self._cur_obj[param_name] = []

                logging.debug(f'self._cur_child_id=={self._cur_child_id}')
                logging.debug(f'self._child_counts=={self._child_counts}')

                # if this parameter is not child object id
                # (as it causes redundant empty values for second type of child object which treated as nested,
                # and because redundant child object parameter which is also child object id is incorrect)
                # if this is not usual parameter, duplicate of child object parameter
                # (parent child object id exists for the parameter, means self._cur_child_id is not empty)
                # and this is not phantom occurrence of child object id parameter
                # (child object id is empty, but subordinate child object parameter exists)
                if not self._is_param_child_id and self._cur_child_id and self._cur_child_id[1]:
                    for i in range(self._child_counts[self._cur_child_id[0]]):  # add proper amount of empty elements
                        self._cur_obj[param_name].append([])                    # (used for proper matching child object parameter values to child object ids,
                                                                                # in case of optional child object parameters)
                        logging.debug(f'Added empty element for child object parameter {param_name} during creation')

                self._cur_obj[param_name].append(param_values)  # save as nested list

                if self._is_new_child_started and self._cur_child_id and self._cur_child_id[1]:  # avoid phantom occurrences of the parameter (with no value)
                    self._param_to_child_id_mapping[param_name] = self._cur_child_id  # save current child object id
                    logging.debug(f'Setting self._param_to_child_id_mapping[{param_name}]={self._param_to_child_id_mapping[param_name]}')

            else:
                self._cur_obj[param_name] = param_values       # if this is plain parameter, just save its value(s)

        try:
            logging.debug(f'Finally self._cur_obj[{param_name}]=={self._cur_obj[param_name]}')
        except KeyError:
            logging.debug(f'Finally self._cur_obj[{param_name}] not set due to empty value')

        # set current child object id value for further child object parameters
        if self._is_param_child_id:
            self._cur_child_id = param_name, param_values[:]  # copy of parameter value(s) list to avoid cross modification
                                                              # by reference due to
                                                              # self._cur_obj[param_name] = param_values above

            logging.debug(f'self._cur_child_id={self._cur_child_id}', )

            if param_values:  # If child object id value present, start new child object (required for cases where child object IDs can have same value)
                for sub_obj_param, saved_sub_obj_id in list(self._param_to_child_id_mapping.items()):
                    if saved_sub_obj_id[0] == self._cur_child_id[0]:
                        self._param_to_child_id_mapping.pop(sub_obj_param)  # This will trigger new child object starting for child object parameter subObjParam

                logging.debug(f'Clearing self._param_to_child_id_mapping for parameters related to child object {param_name} due to _cur_child_id value present')

            if self._cur_child_id[1]:                            # avoiding phantom occurrences of the parameter (with no value)
                try:
                    self._child_counts[param_name] += 1
                except KeyError:
                    self._child_counts[param_name] = 0
                logging.debug(f'self._child_counts[{param_name}]={self._child_counts}')

        logging.debug('Finished _save_param()')


    def _handle_param(self, param_name, param_values):
        """
        This function saves provided parameter either to line parameters buffer,
        in case of object_id_param_names parser parameter provided (needed for its proper support),
        or directly to current result object
        """

        logging.debug(f'Call _handle_param with {(param_name, param_values)}')

        # Update object id
        # if id parameter name changed and
        # if no Object Ids specified by user and no ID parameter saved yet
        # or if parameter is listed in user specified object ids list
        if (self._id_param_name != param_name
            and
            (not (self._object_id_param_names or self._id_param_name)
             or
             param_name in self._object_id_param_names)):

            self._finalize_object()  # finalize current object, if any, because changing object id name means previous object completed
            self._id_param_name = param_name
            logging.debug(f'Object identity detected according to user parameter object_id_param_names, self._idParamName={self._id_param_name}')

            self._child_ids = self._object_relations.get(self._id_param_name, [])  # to handle child objects model

        if param_name == self._id_param_name and param_values:        # Finalize object, if current parameter is non empty object id

            logging.debug('New object id encountered, finalizing object')
            logging.debug(f'self._cur_obj={self._cur_obj}')
            logging.debug(f'param_name={param_name}')
            logging.debug(f'param_values={param_values}')

            self._finalize_object()

        # flag shows whether current parameter is child object identity
        self._is_param_child_id = param_name in self._child_ids
        logging.debug(f'self._is_param_child_id={self._is_param_child_id} for {param_name}')

        # handle save_as_list_of_lists attribute
        try:                # if parameter attribute exists for parameter, take it
            save_as_list_of_lists = self._save_as_list_of_lists_all[param_name]

            logging.debug(f'Found self.__save_as_list_of_lists_all[{param_name}]={self._save_as_list_of_lists_all[param_name]}')

        except KeyError:    # otherwise continue with current object based value (self._save_as_list_of_lists)
            save_as_list_of_lists = self._save_as_list_of_lists_all[param_name] = self._save_as_list_of_lists

            logging.debug(f'Missing self.__save_as_list_of_lists_all[{param_name}], instead using self._save_as_list_of_lists={self._save_as_list_of_lists}')

        # save parameter either to current object or line buffer
        if self._object_id_param_names:
            # custom object id may be not first element in line,
            # so saving to line parameter buffer is needed
            # to detect and handle such situation properly
            self._parsed_param_data[param_name] = (param_values, save_as_list_of_lists)
            logging.debug(f'Added parameter {param_name} to self._parsed_param_data')
            logging.debug(f'self._parsed_param_data={self._parsed_param_data}')
        else:
            # if custom object ids not specified, then default behavior,
            # save result to return
            self._save_param(param_name,
                             param_values,
                             save_as_list_of_lists)

        # if child object was detected, set flag once for next parameters in current object
        if not self._save_as_list_of_lists:
            self._save_as_list_of_lists = self._is_param_child_id
            logging.debug(f'_save_as_list_of_lists={self._save_as_list_of_lists}')

        logging.debug('Finished _handle_param()')


    def _save_line_params(self):
        """
        This function saves parameters collected per line (in case of object_id_param_names parser parameter specified), if any
        """

        logging.debug('call _save_line_params()')

        for param_name, (param_values, save_as_list_of_lists) in self._parsed_param_data.items():

            # flag shows whether current parameter is child object identity
            self._is_param_child_id = param_name in self._child_ids
            logging.debug(f'self._is_param_child_id={self._is_param_child_id} for {param_name}')

            self._save_param(param_name,
                             param_values,
                             save_as_list_of_lists)

        self._parsed_param_data = collections.OrderedDict() if self._keep_order else {}  # Clearing parameter line buffer

        logging.debug('Finish _save_line_params()')


    def _parse_param_line(self, header_line, value_line, all_lines, curr_line_no):
        """
        This function parses parameter values line
        and returns parameters mapped to its values as dictionary.
        """

        logging.debug(f'call _parse_param_line with {(header_line, value_line, '...')}')

        param_names = []  # List of parameter headers in current headerline

        # Parameter's justification
        is_cur_param_l_justified = None
        is_right_param_l_justified = None

        param_values = []  # List with current parameter values

        try:  # if header line found it means it was already parsed, so reusing its parse map
            for param_name, cur_param_val_search_start_pos, cur_param_val_search_end_pos in self._param_parse_map[header_line]:
                logging.debug(f'Analyzing parameter {param_name} by saved map: {(cur_param_val_search_start_pos, cur_param_val_search_end_pos)}')
                param_values = self._split_values_line_to_list(value_line[cur_param_val_search_start_pos:cur_param_val_search_end_pos])
                logging.debug(f'param_values={param_values}')
                self._handle_param(param_name, param_values)

        except KeyError:
            # If such header line not found it means it should be parsed from scratch
            logging.debug(f'Parsing such header_line for first time:\n{header_line}')

            left_param_name_end_pos = -COLUMN_SEPARATOR_SPACES_COUNT  # Initially to start search from 0 position, because of adding COLUMN_SEPARATOR_SPACES_COUNT below
            left_param_val_search_end_pos = 0  # Unlike parameter names, parameter values not necessary must be separated by COLUMN_SEPARATOR_SPACES_COUNT, so no adding 1, so initial value is 0

            # Lists to save data for building parameters parse map
            param_val_search_start_positions = []
            param_val_search_end_positions = []

            param_names = header_line.split()
            logging.debug(f'param_names={param_names}')

            for i in range(len(param_names)):  # Iterating over parameter names from lef to the right
                # Get parameter name
                param_name = param_names[i]

                logging.debug(f'analyzing for first time parameter param_name={param_name}')

                # Get start and end (non inclusive!) positions for parameter name (header)

                # Search with Start and End positions to avoid collisions during search and for speed up
                cur_param_name_start_pos = header_line.index(param_name, left_param_name_end_pos + COLUMN_SEPARATOR_SPACES_COUNT)
                logging.debug(f'curParamNameStartPos={cur_param_name_start_pos}')

                cur_param_name_end_pos = cur_param_name_start_pos + len(param_name)  # Calculate position of header's last character
                logging.debug(f'curParamNameEndPos={cur_param_name_end_pos}')

                cur_param_val_search_start_pos = left_param_val_search_end_pos
                logging.debug(f'cur_param_val_search_start_pos={cur_param_val_search_start_pos}')

                # ************ CALCULATING cur_param_val_search_end_pos ************

                # Get characteristics from right parameter, which are necessary below
                try:
                    right_param_name = param_names[i + 1]
                    right_param_name_start_pos = header_line.index(right_param_name,
                                                                   cur_param_name_end_pos + COLUMN_SEPARATOR_SPACES_COUNT)

                    right_param_name_end_pos = right_param_name_start_pos + len(right_param_name)

                except IndexError:
                    right_param_name = None
                    right_param_name_start_pos = None

                # Check if parameter value is right justified to its header
                if is_right_param_l_justified == None:       # if value is not valid
                    # Calculate property, if not previously saved
                    is_cur_param_l_justified = self._is_param_l_justified(param_name,
                                                                          cur_param_name_start_pos,
                                                                          cur_param_name_end_pos,
                                                                          right_param_name_start_pos,
                                                                          all_lines,
                                                                          curr_line_no)
                    logging.debug(f'Calculated is_cur_param_l_justified for parameter {param_name}')
                else:
                    # Reuse property collected on previous iteration
                    is_cur_param_l_justified = is_right_param_l_justified
                    logging.debug(f'Reused parameter is_cur_param_l_justified=is_right_param_l_justified={is_cur_param_l_justified} for parameter {param_name}')

                if is_cur_param_l_justified:

                    logging.debug(f'Parameter {param_name} is left justified')

                    # to find end values position, next parameter adjustment check required
                    if right_param_name:
                        logging.debug(f'right_param_name={right_param_name}')

                        # Detecting characteristics of next right parameter
                        # for is_param_l_justified method
                        try:
                            right_right_param_name_start_pos = header_line.index(param_names[i + 2],  # right-right parameter name
                                                                                 right_param_name_end_pos + COLUMN_SEPARATOR_SPACES_COUNT)
                        except IndexError:
                            right_right_param_name_start_pos = None

                        is_right_param_l_justified = self._is_param_l_justified(right_param_name,
                                                                                right_param_name_start_pos,
                                                                                right_param_name_end_pos,
                                                                                right_right_param_name_start_pos,
                                                                                all_lines,
                                                                                curr_line_no)

                        logging.debug(f'is_right_param_l_justified={is_right_param_l_justified}')

                        if is_right_param_l_justified:
                            # in case next right parameter from current one is also left justified,
                            # take cur_param_val_search_end_pos as right_param_name_start_pos bcoz parameter value may be limited by right side parameter
                            cur_param_val_search_end_pos = right_param_name_start_pos
                            logging.debug(f'Right parameter is left justified, cur_param_val_search_end_pos={cur_param_val_search_end_pos}')
                        else:
                            # In case of adjustment change, its unknown where current parameter values end and where next parameter's values begin,
                            # So rest of the lines containing corresponding parameters values are scanned,
                            # evaluating top right position for current parameter
                            logging.debug('Adjustment change, start of searching cur_param_val_max_end_pos')

                            cur_param_val_max_end_pos = None
                            is_line_cur_param_related = True   # flag indicating current line contains current parameter's value
                            prev_line = None                   # previous line

                            for j in range(curr_line_no, len(all_lines)):

                                cur_line = all_lines[j]

                                if prev_line != '':  # value lines should not be preceded by empty line

                                    # consider only lines containing values related to corresponding header line
                                    # and only in case both current parameter and right parameter present (if line end reaches right parameter column)
                                    if is_line_cur_param_related \
                                       and \
                                       len(cur_line) >= right_param_name_start_pos:

                                        logging.debug(f'cur_line={cur_line}')

                                        try:
                                            # get border of parameter values as rindex of column separator occurrence between current and right parameter headers
                                            cur_param_val_search_end_pos = cur_line.rindex(' ' * COLUMN_SEPARATOR_SPACES_COUNT,
                                                                                           cur_param_name_start_pos,
                                                                                           right_param_name_start_pos)
                                            logging.debug(f'cur_param_val_search_end_pos={cur_param_val_search_end_pos}')

                                            if not cur_param_val_max_end_pos:  # only once
                                                cur_param_val_max_end_pos = cur_param_val_search_end_pos

                                            # since in case detected FIRST right space is closer to left
                                            # it means that right hand parameter starts more to the left side, so minimum value taken
                                            cur_param_val_max_end_pos = min(cur_param_val_search_end_pos, cur_param_val_max_end_pos)
                                            logging.debug(f'cur_param_val_max_end_pos={cur_param_val_max_end_pos}')

                                        except ValueError:

                                            logging.debug('Parameter value close up to right parameter column, end search')

                                            # If space found between parameters, it means current parameter value
                                            # terminated by next column parameter
                                            cur_param_val_max_end_pos = right_param_name_start_pos
                                            break  # Since this is maximum possible value, exit from loop
                                else:
                                    # If previous line is empty, current line is a header line,
                                    # so check if further vales lines will be related to current parameter
                                    # (if header contains parameter name in the right place)
                                    is_line_cur_param_related = cur_line[cur_param_name_start_pos:cur_param_name_end_pos] == param_name

                                prev_line = cur_line  # save previous line for next iteration

                            # end = max right margin
                            cur_param_val_search_end_pos = cur_param_val_max_end_pos
                            logging.debug(f'Search due to changed justification found\ncur_param_val_search_end_pos={cur_param_val_search_end_pos}')

                    else:  # Means no next (right) parameter
                        cur_param_val_search_end_pos = None
                        logging.debug(f'No next (right) parameter,\n'
                                      'cur_param_val_search_end_pos={cur_param_val_search_end_pos}')

                else:  # Parameter is right justified
                    logging.debug(f'Parameter {param_name} is right justified')
                    cur_param_val_search_end_pos = cur_param_name_end_pos  # end is cur_param_name_end_pos
                    logging.debug(f'cur_param_val_search_end_pos={cur_param_val_search_end_pos}')
                    is_right_param_l_justified = None  # marking value as not valid, so it will be recalculated on next iterations, if needed

                # ************ END CALCULATING cur_param_val_search_end_pos ************


                logging.debug(f'Taking values in range {cur_param_val_search_start_pos}:{cur_param_val_search_end_pos}')

                param_values = self._split_values_line_to_list(value_line[cur_param_val_search_start_pos:cur_param_val_search_end_pos])
                logging.debug(f'param_values={param_values}')

                self._handle_param(param_name, param_values)

                # Building lists for parse map
                param_val_search_start_positions.append(cur_param_val_search_start_pos)
                param_val_search_end_positions.append(cur_param_val_search_end_pos)

                # save necessary data for next iteration
                left_param_name_end_pos  = cur_param_name_end_pos
                left_param_val_search_end_pos   = cur_param_val_search_end_pos

            # save parse parameters for current header line
            self._param_parse_map[header_line] = list(zip(param_names, param_val_search_start_positions, param_val_search_end_positions))

        # save parameters in line buffer, if any
        self._save_line_params()


    def _parse_horizontal_line(self, line):
        """
        This function parses horizontal parameters
        (defined by parser parameter hor_param_names)
        """

        logging.debug(f'Call _parse_horizontal_line{(line,)}')
        logging.debug(f'self._cur_obj={self._cur_obj}')
        logging.debug(f'self._hor_param_names={self._hor_param_names}')

        # Initially just split by spaces
        tokens = self._split_values_line_to_list(line)

        logging.debug(f'tokens={tokens}')

        param_name = None
        param_values = []

        for token in tokens:
            logging.debug(f'Processing token {token}')

            if token in self._hor_param_names:
                if param_name:  # in case of new parameter name encountered, save current parameter and its values
                    self._handle_param(param_name, param_values)

                # and switch to new parameter
                param_name = token
                param_values = []
            else:
                param_values.extend(self._split_values_line_to_list(token))

        # save last parameter, as it cannot be handled in above loop
        self._handle_param(param_name, param_values)

        # save parameters in line buffer, if any
        self._save_line_params()

        logging.debug('Finished _parse_horizontal_line()')
        logging.debug(f'self._cur_obj={self._cur_obj}')


    def parse(self, text):
        """
        This is worker function. It takes printout as string and
        iterates over sequence of lines - the result of its splitlines() call on printout.
        """
        logging.debug(f'parse() started')
        text_lines = [l.strip() for l in text.splitlines()]
        logging.debug(f'text_lines:\n{text_lines}')

        cur_header_line = ''  # cur_header_line should not initially be equal to prev_line
        prev_line = None

        for i in range(len(text_lines)):
            line = text_lines[i]

            logging.debug(f'Handling line:\n{line}')
            logging.debug(f'i={i}')

            if i > 0:
                prev_line = text_lines[i - 1]

            try:
                next_line = text_lines[i + 1]
            except IndexError:
                next_line = None

            try:
                next_next_line = text_lines[i + 2]
            except IndexError:
                next_next_line = None

            if line or prev_line == cur_header_line:  # do not handle empty line if previous one is not current header line
                                                      # since empty line should only be handled in case it is value line,
                                                      # meaning previous line should be current header line
                if bool(set(re.split(self._value_delimiters, line)) & set(self._hor_param_names)):
                    logging.debug('Horizontal parameters found')
                    self._parse_horizontal_line(line)

                elif not prev_line: # If previous line is empty

                    if not next_line and next_next_line:
                        # if next line is empty as well
                        # (but not next after next,
                        # otherwise it is header line
                        # with empty values next to it),
                        # it is threaded as new printout section,
                        # which in turn is handled as new printout

                        logging.debug(f'Section found: {line}')

                        if not self._object_id_param_names:  # if id parameter name not specified by user,
                            self._finalize_object()          # save current object
                            self._id_param_name = None       # prepare for saving new object id from new section
                    else:
                        cur_header_line = line  # means current line is header line

                else:  # current line is parameter values line
                    logging.debug('Handling parameter values')
                    self._parse_param_line(cur_header_line, line, text_lines, i)
                    logging.debug('_parse_param_line finished')

            logging.debug('****** PRINTOUT LINE HANDLING SUMMARY ******')
            logging.debug(f'prev_line={repr(prev_line)}')
            logging.debug(f'line={repr(line)}')
            logging.debug(f'next_line={repr(next_line)}')
            logging.debug(f'cur_header_line={repr(cur_header_line)}')
            logging.debug(f'self._cur_obj={self._cur_obj}')
            logging.debug(f'self.__result_object_list={self._result_object_list}')

        self._finalize_object()  # saving last object data before return
        logging.debug('Finished iterating over printout lines')
        return self._result_object_list
