OutParse — configurable fast printout (text table) parser
=========================================================

Overview
--------
OutParse parses human-readable, line-wrapped printouts (text tables)
and converts them into structured Python data.

It has no external dependencies and is suitable for embedded environments
where pip usage is limited.

A printout represents logically tabular data (rows and columns) that may be:
 - wrapped across multiple lines
 - split into logical sections
 - mixed with horizontal key–value parameters
 - nested (parent/child objects)

The parser output is always a list of dictionaries.


Quick Start
-----------
Example:

```python
from outparse import PrintoutParser

text = '''
POINTS

NAME   LOCATION   TYPE
DotA   100, 88    p

STATUS ACTIVE

NAME   LOCATION   TYPE
PointB 155, 25    p

STATUS PASSIVE

USERS

Username       Email
John Doe       john_doe@www.org
'''

parser = PrintoutParser(hor_param_names=["STATUS"])
result = parser.parse(text)
```

Result:

```python
[
    {
        'NAME': ['DotA'],
        'LOCATION': ['100', '88'],
        'TYPE': ['p'],
        'STATUS': ['ACTIVE'],
        'object_id_param_name': 'NAME'
    },
    {
        'NAME': ['PointB'],
        'LOCATION': ['155', '25'],
        'TYPE': ['p'],
        'STATUS': ['PASSIVE'],
        'object_id_param_name': 'NAME'
    },
    {
        'Username': ['John', 'Doe'],
        'Email': ['john_doe@www.org'],
        'object_id_param_name': 'Username'
    }
]
```


What is a printout/text table?
------------------------------
A printout (aka text table) is a human-readable representation of tabular data
where rows may span multiple lines, but column semantics remain consistent.

Even when visually wrapped, such a printout can always be normalized
into a flat table structure without losing information.

Wrapped form (printout):

```
    NAME   LOCATION   TYPE
    DotA   100, 88    p

    STATUS ACTIVE
```

Logical flat form (text table):

```
    NAME   LOCATION   TYPE   STATUS
    DotA   100, 88    p      ACTIVE
```


Parameters
----------
A parameter is a named field with one or more values.

 - Values are always stored as lists.
 - Multiple values are separated by delimiters (spaces or commas by default.
 - Splitting behavior is configurable via value_delimiters.
 - Set value_delimiters=None or '' to disable splitting.


Vertical and Horizontal Parameters
----------------------------------
Vertical parameters:
   Values aligned under a header row.
    
Example:

        X  Y
        10 15

Horizontal parameters:
    Parameters whose name and value appear on the same line.

Example:
    
        NAME John Doe

Horizontal parameters are NOT auto-detected and must be explicitly
declared via hor_param_names.


Objects and Identifiers
-----------------------
Each parsed object corresponds to one logical row of data.

An object is identified by an identifier parameter (e.g. NAME, ID).

Default behavior:
 - The first detected parameter becomes the identifier.
 - When the same identifier parameter appears again with
   a non-empty value, a new object is started.

If object_id_param_names is provided:
 - Only listed parameters are treated as identifiers.
 - Section changes do not reset identifier detection automatically.


Printout Logical Sections
-------------------------
A single non-empty line surrounded by empty lines starts a new section.
Sections may contain a different object type.

When a new section starts:
 - the current object is finalized
 - identifier detection restarts (unless custom identifiers are specified)

Example:

```
    POINTS

        NAME   LOCATION   TYPE
        pointA 155, 25    n

    USER DATA

        USERNAME   EMAIL
        John       john@mail.com
```


Child Objects (Advanced)
------------------------
OutParse supports hierarchical parent–child relationships.

Its used when one object (parent) contains one or more nested objects (childs).

Example

```
    DEPARTMENTS

        Department            Manager
        Macrodata Refinement  Mark.S

        Employee              Role
        Mark.S                Refiner
        Dylan.G               Refiner
        Irving.B              Refiner
        Helly.R               Refiner

        Department            Manager
        Optics & Design       Burt.G

        Employee              Role
        Burt.G                Designer
        Felicia               Technician
```

Here we have two object types: Department (parent) and Employee (child), to parse it properly, this should be configured via object_relations: 

```python
parser = PrintoutParser(object_relations={'Department': ['Employee']})
result = parser.parse(text)
print(result)
```

Which results in

```python
[
    {
        'Department': ['Macrodata', 'Refinement'],
        'Manager': ['Mark.S'],
        'Employee': ['Mark.S', 'Dylan.G', 'Irving.B', 'Helly.R'],
        'Role': [
            ['Refiner'],
            ['Refiner'],
            ['Refiner'],
            ['Refiner']
        ],
        'object_id_param_name': 'Department'
    },
    {
        'Department': ['Optics', '&', 'Design'],
        'Manager': ['Burt.G'],
        'Employee': ['Burt.G', 'Felicia'],
        'Role': [
            ['Designer'],
            ['Technician']
        ],
        'object_id_param_name': 'Department'
    }
]
```

Child parameters are stored as lists of lists,
aligned by child identifier index.

Hierarchy is configured via object_relations:

```python
    {
        "PARENT_ID": ["CHILD_ID_1", "CHILD_ID_2"]
    }
```

where "PARENT_ID" is the identifier parameter name of the parent object type,
and ["CHILD_ID_1", "CHILD_ID_2"] is a list of identifier parameter names for all child object types
that belong to this parent — including indirect descendants (children, grandchildren, etc.).
Nesting level does not matter: any identifier listed here will be treated as a child of "PARENT_ID".


Basic Output Format
-------------------
The parser returns:

`List[Dict[str, List[str]]]`

Each dictionary represents one parsed object and contains:
 - parameter names as keys
 - lists of values as values
 - "object_id_param_name" storing object identifier parameter name


Common Mistakes / Requirements
------------------------------

1. Header line must be separated from previous content (if any) by an empty line

   Incorrect:
   ```
       <previous data>
       NAME   LOCATION   TYPE
   ```

   Correct:
   ```
       <previous data>

       NAME   LOCATION   TYPE
   ```


2. Section title must be separated from previous content (if any) by an empty line
   and must always be followed by an empty line

   Incorrect:

   ```
       <previous data>
       POINTS
       NAME   LOCATION   TYPE
   ```

   Correct:

   ```
       <previous data>

       POINTS

       NAME   LOCATION   TYPE
   ```

3. Text must be space-formatted

   Parsing relies on column positioning.
   If text is tab-formatted, replace tabs with spaces before parsing:

   ```
       text_for_parsing = text.replace('\t', 4 * ' ')
   ```

## License

This project is licensed under the BSD 3-Clause License.  
See the [LICENSE](LICENSE) file for details.