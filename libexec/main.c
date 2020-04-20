#include <stdio.h>
#include <string.h>
#include <ctype.h>

#include "lzhuf.h"

int main(int argc, char *argv[])
{
        char  *s;

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
                Encode(0, argv[2], argv[3], huf, 0);
        else
                Decode(0, argv[2], argv[3], huf, 0);

        FreeStruct(huf);

        return 0;
}
