/*
 Copyright 2020 Marius Petrescu, YO2LOJ <marius@yo2loj.ro>

 This program is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/

/*
    To compile the files under Windows use OpenWatcom C
    You need to define LZHUF in your project setup

    On Linux, just issue a 'make' command
*/



#include <stdio.h>
#include <string.h>
#include <ctype.h>

#include "lzhuf.h"

int main(int argc, char *argv[])
{
        char  *s;
        int result;

        struct lzhufstruct * huf = AllocStruct();


        if (argc != 4) {
                printf("'lzhuf e file1 file2' encodes file1 into file2.\n"
                           "'lzhuf d file2 file1' decodes file2 into file1.\n");
                return 1;
        }
        if (s = argv[1], s[1] || strpbrk(s, "DEde") == NULL) {
                printf("??? %s\n", s);
                return 1;
        }
        if (toupper(*argv[1]) == 'E')
                result = Encode(0, argv[2], argv[3], huf, 0);
        else
                result = Decode(0, argv[2], argv[3], huf, 0);

        FreeStruct(huf);

        if (result != 0) result = 1;

        return result;
}
