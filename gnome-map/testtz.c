#include <stdio.h>
#include <unistd.h>
#include <time.h>


int main()
{

    tzset ();
    printf ("%s %s %ld %d\n",tzname[0],tzname[1], timezone, daylight);
}
