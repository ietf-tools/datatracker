#include <stdio.h>

int main( void )
{
    int c;
    int count = 0;

    //turn off buffering
    setvbuf(stdin, NULL, _IONBF, 0);
    setvbuf(stdout, NULL, _IONBF, 0);
    setvbuf(stderr, NULL, _IONBF, 0);

    c = getchar();
    while(c != EOF)
    {
	if (c == '.') count++;
	putchar(c);
	if ( count % 76 == 0) {
	    fprintf(stderr, "%4d", count);
	}
	c = getchar();
    }
    return 0;
}
