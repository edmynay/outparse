OutParse — configurable fast printout/text table parser
=======================================================

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
POINTS DATA

NAME   LOCATION   TYPE
DotA   100, 88    p

STATUS ACTIVE

NAME   LOCATION   TYPE
PointB 155        p
       200000

STATUS PASSIVE

USER DATA

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
A printout/text table is a human-readable representation of tabular data
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

 - Parameter names should not contain spaces
 - Values are always stored as lists.
 - Multiple values are separated by delimiters (spaces or commas by default.
 - Splitting behavior is configurable via value_delimiters.
 - Set value_delimiters='' to disable splitting.


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
A section title is an optional single non-empty line used to group objects.

If present, it must be separated from previous content (if any) by an empty
line and followed by an empty line before the section content.

Sections may introduce a different object type.

In Quick Start chapter's Example there are two sections: POINTS DATA and USER DATA.


Child Objects (Advanced)
------------------------
OutParse supports hierarchical parent–child relationships.

It is used when one object (parent) contains one or more nested child objects.

Example

```
    DEPARTMENTS

        Department            Manager
        Macrodata Refinement  Mark.S

        Employee              Role
        Mark.S                Refiner, Manager
        Dylan.G               Refiner
        Irving.B              Refiner
        Helly.R               Refiner

        Department            Manager
        Optics & Design       Burt.G

        Employee              Role
        Burt.G                Designer, Manager
        Felicia               Technician
```

Here we have two object types: Department (parent) and Employee (child). To parse this hierarchy correctly, configure the relation via object_relations: 

```python
parser = PrintoutParser(object_relations={'Department': ['Employee']}, value_delimiters=',')
result = parser.parse(text)
print(result)
```

Which results in:

```python
[
    {
        'Department': ['Macrodata Refinement'],
        'Manager': ['Mark.S'],
        'Employee': ['Mark.S', 'Dylan.G', 'Irving.B', 'Helly.R'],
        'Role': [
            ['Refiner', 'Manager'],
            ['Refiner'],
            ['Refiner'],
            ['Refiner']
        ],
        'object_id_param_name': 'Department'
    },
    {
        'Department': ['Optics & Design'],
        'Manager': ['Burt.G'],
        'Employee': ['Burt.G', 'Felicia'],
        'Role': [
            ['Designer', 'Manager'],
            ['Technician']
        ],
        'object_id_param_name': 'Department'
    }
]
```

Child parameters are stored as lists of lists and follow the same order as child object identifiers.

This means that each child parameter value can be accessed by the same index as the corresponding child object id.

Example:

```python
employees = result[0]['Employee']
roles = result[0]['Role']

for i, employee in enumerate(employees):
    role = ', '.join(roles[i])
    print(f"Employee {employee} role is {role}")
```

Output:

```python
Employee Mark.S role is Refiner, Manager
Employee Dylan.G role is Refiner
Employee Irving.B role is Refiner
Employee Helly.R role is Refiner
```

Hierarchy is configured via object_relations, for example:

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
   Parsing relies on fixed column spacing.

   If parameter names contain spaces, replace them (e.g. with underscores).

   Tab characters are automatically normalized before parsing using the
   configured `tab_size` (default: 4), so tab-formatted input is converted
   to space-aligned text internally.

## License

This project is licensed under the BSD 3-Clause License.  
See the [LICENSE](LICENSE) file for details.