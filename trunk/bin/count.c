#include <stdio.h>

int main( void )
{
    int c;
    int count = 0;

    //turn off buffering
    setvbuf(stdin, NULL, _IONBF, 0);
    setvbuf(stdout, NULL, _IONBF, 0);
    setvbuf(stderr, NULL, _IONBF, 0);

    c = fgetc(stdin);
    while(c != EOF)
    {
	if (c=='.' || c=='E' || c=='F' || c=='s') count++; else count=0;
	fputc(c, stdout);
	fflush(stdout);
	if (count && count % 76 == 0) {
	    fprintf(stderr, "%4d\n", count);
	    fflush(stderr);
	}
	c = fgetc(stdin);
    }
    return 0;
}
