static void
doNewtInit (int *width, int *height)
{
	newtInit ();
	newtCls ();
	newtGetScreenSize (width, height);
	newtDrawRootText (0, 0, "Red Hat Linux for S/390   (C) 2001 Red Hat, Inc.");
}
