# Copyright (C) 2022 Alexandre Mitsuru Kaihara
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.


# Brief: This exception is for in case the terminal input is incorrect
class InvalidCommandLineInput(Exception):
    pass

# Brief: This expection is related a invalid parameter
class MissingObjectParameter(Exception):
    pass

# Brief: This exception is related to a failure during docker container instantiation 
class NodeInstantiationFailed(Exception):
    pass

# Brief: This exception is related to the creation of a 
class InvalidNodeName(Exception):
    pass