/* header file for S-Lang internal structures that users do not (should not)
   need.  Use slang.h for that purpose. */
/* Copyright (c) 1992, 1998 John E. Davis
 * This file is part of the S-Lang library.
 *
 * You may distribute under the terms of either the GNU General Public
 * License or the Perl Artistic License.
 */

#include "config.h"

#include <string.h>

#include "jdmacros.h"
#include "sllimits.h"

#ifdef VMS
# define SLANG_SYSTEM_NAME "_VMS"
#else
# if defined (IBMPC_SYSTEM)
#  define SLANG_SYSTEM_NAME "_IBMPC"
# else
#  define SLANG_SYSTEM_NAME "_UNIX"
# endif
#endif  /* VMS */


/* These quantities are main_types for byte-compiled code.  They are used
 * by the inner_interp routine.  The _BC_ means byte-code.
 */

#define _SLANG_BC_LVARIABLE	SLANG_LVARIABLE
#define _SLANG_BC_GVARIABLE	SLANG_GVARIABLE
#define _SLANG_BC_IVARIABLE 	SLANG_IVARIABLE
#define _SLANG_BC_RVARIABLE	SLANG_RVARIABLE
#define _SLANG_BC_INTRINSIC 	SLANG_INTRINSIC
#define _SLANG_BC_FUNCTION  	SLANG_FUNCTION
#define _SLANG_BC_MATH_UNARY	SLANG_MATH_UNARY
#define _SLANG_BC_APP_UNARY	SLANG_APP_UNARY

#define _SLANG_BC_BINARY	0x10
#define _SLANG_BC_LITERAL	0x11           /* constant objects */
#define _SLANG_BC_LITERAL_INT	0x12
#define _SLANG_BC_LITERAL_STR	0x13
#define _SLANG_BC_BLOCK		0x14

/* These 3 MUST be in this order too ! */
#define _SLANG_BC_RETURN	0x15
#define _SLANG_BC_BREAK		0x16
#define _SLANG_BC_CONTINUE	0x17

#define _SLANG_BC_EXCH		0x18
#define _SLANG_BC_LABEL		0x19
#define _SLANG_BC_LOBJPTR	0x1A
#define _SLANG_BC_GOBJPTR	0x1B
#define _SLANG_BC_X_ERROR	0x1C
/* These must be in this order */
#define _SLANG_BC_X_USER0	0x1D
#define _SLANG_BC_X_USER1	0x1E
#define _SLANG_BC_X_USER2	0x1F
#define _SLANG_BC_X_USER3	0x20
#define _SLANG_BC_X_USER4	0x21

#define _SLANG_BC_ARGS_END_DIRECTIVE	0x22
#define _SLANG_BC_ARGS_START_DIRECTIVE	0x23
#define _SLANG_BC_CALL_DIRECT		0x24
#define _SLANG_BC_CALL_DIRECT_FRAME	0x25
#define _SLANG_BC_UNARY			0x26


#define _SLANG_BC_DEREF_ASSIGN		0x30
#define _SLANG_BC_SET_LOCAL_LVALUE	0x31
#define _SLANG_BC_SET_GLOBAL_LVALUE	0x32
#define _SLANG_BC_SET_INTRIN_LVALUE	0x33
#define _SLANG_BC_SET_STRUCT_LVALUE	0x34
#define _SLANG_BC_FIELD			0x35

#define _SLANG_BC_LINE_NUM		0x40

/* Byte-Code Sub Types (_BCST_) */

/* These are sub_types of _SLANG_BC_BLOCK */
#define _SLANG_BCST_ERROR_BLOCK	0x01
#define _SLANG_BCST_EXIT_BLOCK	0x02
#define _SLANG_BCST_USER_BLOCK0	0x03
#define _SLANG_BCST_USER_BLOCK1	0x04
#define _SLANG_BCST_USER_BLOCK2	0x05
#define _SLANG_BCST_USER_BLOCK3	0x06
#define _SLANG_BCST_USER_BLOCK4	0x07
/* The user blocks MUST be in the above order */
#define _SLANG_BCST_LOOP	0x10
#define _SLANG_BCST_WHILE	0x11
#define _SLANG_BCST_FOR		0x12
#define _SLANG_BCST_FOREVER	0x13
#define _SLANG_BCST_CFOR	0x14
#define _SLANG_BCST_DOWHILE	0x15
#define _SLANG_BCST_IF		0x20
#define _SLANG_BCST_IFNOT	0x21
#define _SLANG_BCST_ELSE	0x22
#define _SLANG_BCST_ANDELSE	0x23
#define _SLANG_BCST_ORELSE	0x24
#define _SLANG_BCST_SWITCH	0x25

/* assignment (_SLANG_BC_SET_*_LVALUE) subtypes.  The order MUST correspond
 * to the assignment token order with the ASSIGN_TOKEN as the first!
 */
#define _SLANG_BCST_ASSIGN		0x01
#define _SLANG_BCST_PLUSEQS		0x02
#define _SLANG_BCST_MINUSEQS		0x03
#define _SLANG_BCST_PLUSPLUS		0x04
#define _SLANG_BCST_POST_PLUSPLUS	0x05
#define _SLANG_BCST_MINUSMINUS		0x06
#define _SLANG_BCST_POST_MINUSMINUS	0x07


/* These use SLANG_PLUS, SLANG_MINUS, SLANG_PLUSPLUS, etc... */


typedef union
{
   long l_val;
   VOID_STAR p_val;
   char *s_val;
   int i_val;
   SLang_MMT_Type *ref;
   SLang_Name_Type *n_val;
#if SLANG_HAS_FLOAT
   double f_val;
#endif
   struct _SLang_Struct_Type *struct_val;
   struct _SLang_Array_Type *array_val;
}
_SL_Object_Union_Type;

typedef struct
{
   unsigned char data_type;	       /* SLANG_INT_TYPE, ... */
   _SL_Object_Union_Type v;
}
SLang_Object_Type;


struct _SLang_MMT_Type
{
   unsigned char data_type;	       /* int, string, etc... */
   VOID_STAR user_data;	       /* address of user structure */
   unsigned int count;		       /* number of references */
};

extern int _SLang_pop_object_of_type (unsigned char, SLang_Object_Type *);


typedef struct
{
   char *name;			       /* slstring */
   SLang_Object_Type obj;
}
_SLstruct_Field_Type;

typedef struct _SLang_Struct_Type
{
   _SLstruct_Field_Type *fields;
   unsigned int nfields;	       /* number used */
   unsigned int num_refs;
}
_SLang_Struct_Type;

extern void _SLstruct_delete_struct (_SLang_Struct_Type *);
extern int _SLang_push_struct (_SLang_Struct_Type *);
extern int _SLang_pop_struct (_SLang_Struct_Type **);
extern int _SLstruct_init (void);
extern SLang_Object_Type *_SLstruct_get_assign_obj (char *);
extern int _SLstruct_get_field (char *);
extern int _SLstruct_define_struct (void);
extern int _SLstruct_define_typedef (void);
extern int _SLstruct_create_struct (unsigned int,
				    char **,
				    unsigned char *,
				    VOID_STAR *);

extern int _SLang_push_void_star (unsigned char, VOID_STAR);
extern int _SLang_push_i_val (unsigned char, int);
extern int _SLang_pop_i_val (unsigned char, int *);

extern int _SLang_pop_datatype (unsigned char *);
extern int _SLang_push_datatype (unsigned char);


struct _SLang_Ref_Type
{
   int is_global;
   union
     {
	SLang_Name_Type *nt;
	SLang_Object_Type *local_obj;
     }
   v;
};

extern int _SLang_dereference_ref (SLang_Ref_Type *);
extern int _SLang_deref_assign (SLang_Ref_Type *);
extern int _SLang_push_ref (int, VOID_STAR);

extern SLang_Object_Type *_SLStack_Pointer;
extern int SLang_pop(SLang_Object_Type *);
extern void SLang_free_object (SLang_Object_Type *);

extern int _SLpush_slang_obj (SLang_Object_Type *);

extern char *_SLexpand_escaped_char(char *, char *);
extern void _SLexpand_escaped_string (char *, char *, char *);

extern int _SLreverse_stack (int);
extern int _SLroll_stack (int);
/* If argument *p is positive, the top |*p| objects on the stack are rolled
 * up.  If negative, the stack is rolled down.
 */

extern int _SLang_apropos (char *, unsigned int);

/* returns a pointer to an SLstring string-- use SLang_free_slstring */
extern char *_SLstringize_object (SLang_Object_Type *);
extern int _SLdump_objects (char *, SLang_Object_Type *, unsigned int, int);

extern int _SLarray_aput (void);
extern int _SLarray_aget (void);
extern int _SLarray_inline_implicit_array (void);
extern int _SLarray_inline_array (void);
extern int
_SLarray_typecast (unsigned char, VOID_STAR, unsigned int,
		   unsigned char, VOID_STAR, int);


extern SLang_Object_Type *_SLRun_Stack;
extern SLang_Object_Type *_SLStack_Pointer;

extern int _SLang_Trace;
extern int _SLstack_depth(void);
extern char *_SLang_Current_Function_Name;

extern int _SLang_trace_fun(char *);
extern int _SLang_Compile_Line_Num_Info;

extern char *_SLstring_dup_hashed_string (char *, unsigned long);
extern unsigned long _SLcompute_string_hash (char *);
extern char *_SLstring_make_hashed_string (char *, unsigned int, unsigned long *);
extern void _SLfree_hashed_string (char *, unsigned int, unsigned long);
unsigned long _SLstring_hash (unsigned char *, unsigned char *);
extern int _SLinit_slcomplex (void);

/* frees upon error.  NULL __NOT__ ok. */
extern int _SLang_push_slstring (char *);

extern int SLang_push(SLang_Object_Type *);
extern int SLadd_global_variable (char *);
extern void _SLang_clear_error (void);

extern int _SLdo_pop (void);
extern unsigned int _SLsys_getkey (void);
extern int _SLsys_input_pending (int);
#ifdef IBMPC_SYSTEM
extern unsigned int _SLpc_convert_scancode (unsigned int);
#endif
#ifdef REAL_UNIX_SYSTEM
extern int SLtt_tigetflag (char *, char **);
extern int SLtt_tigetnum (char *, char **);
extern char *SLtt_tigetstr (char *, char **);
extern char *SLtt_tigetent (char *);
#endif

extern unsigned char SLang_Input_Buffer [SL_MAX_INPUT_BUFFER_LEN];

extern int _SLregister_types (void);
extern SLang_Class_Type *_SLclass_get_class (unsigned char);
extern VOID_STAR _SLclass_get_ptr_to_value (SLang_Class_Type *, SLang_Object_Type *);
extern void _SLclass_type_mismatch_error (unsigned char, unsigned char);
extern int _SLclass_init (void);
extern int _SLclass_typecast (unsigned char, int, int);

extern unsigned char _SLclass_Class_Type [256];

extern int (*_SLclass_get_typecast (unsigned char, unsigned char, int))
(unsigned char, VOID_STAR, unsigned int,
 unsigned char, VOID_STAR);

extern int (*_SLclass_get_binary_fun (int, SLang_Class_Type *, SLang_Class_Type *, SLang_Class_Type **))
(int,
 unsigned char, VOID_STAR, unsigned int,
 unsigned char, VOID_STAR, unsigned int,
 VOID_STAR);

extern int (*_SLclass_get_unary_fun (int, SLang_Class_Type *, SLang_Class_Type **, int))
(int, unsigned char, VOID_STAR, unsigned int, VOID_STAR);

extern int _SLarray_add_bin_op (unsigned char type);

extern int _SLang_call_funptr (SLang_Name_Type *);
extern void _SLset_double_format (char *);

extern char *_SLdefines[];


extern int _SLerrno_errno;
extern int _SLerrno_init (void);

typedef struct _SLang_Array_Type
{
   unsigned char data_type;
   unsigned int sizeof_type;
   VOID_STAR data;
   unsigned int num_elements;
   unsigned int num_dims;
   int dims [SLARRAY_MAX_DIMS];
   VOID_STAR (*index_fun)_PROTO((struct _SLang_Array_Type *, int *));
   /* This function is designed to allow a type to store an array in
    * any manner it chooses.  This function returns the address of the data
    * value at the specified index location.
    */
   unsigned int flags;
#define DATA_VALUE_IS_READ_ONLY		1
#define DATA_VALUE_IS_POINTER		2
#define DATA_VALUE_IS_RANGE		4
#define DATA_VALUE_IS_INTRINSIC		8
   SLang_Class_Type *cl;
   unsigned int num_refs;
}
SLang_Array_Type;

extern int SLang_pop_array (SLang_Array_Type **, int);
extern int SLang_push_array (SLang_Array_Type *, int);
extern void SLang_free_array (SLang_Array_Type *);
extern int _SLarray_init_slarray (void);
extern SLang_Array_Type *SLang_create_array (unsigned char, int, VOID_STAR, int *, unsigned int);

extern int _SLcompile_push_context (void);
extern int _SLcompile_pop_context (void);
extern int _SLang_Auto_Declare_Globals;

#if 1
typedef struct
{
   unsigned char type;
   union
     {
	int i_val;
	char *s_val;		       /* Used for IDENT_TOKEN, FLOAT, etc...  */
     } v;
   int free_sval_flag;
   unsigned int num_refs;
   unsigned long hash;
#if _SLANG_HAS_DEBUG_CODE
   int line_number;
#endif
}
_SLang_Token_Type;

extern void _SLcompile (_SLang_Token_Type *);
extern void (*_SLcompile_ptr)(_SLang_Token_Type *);

/* *** TOKENS *** */

/* If value of any token is changed, the following arrays must be also modified
 * 	Variable		File
 * 	---------------------------------
 * 	Reserved_Keywords_Type	sltoken.c
 * 	Ops_Type		sltoken.c
 * 	Comp_Func_Index 	slang.c
 * 	Op_Types 		slang.c
 * 	Directives_Type 	slang.c
 */

/* Note that that tokens corresponding to ^J, ^M, and ^Z should not be used.
 * This is because a file that contains any of these characters will
 * have an OS dependent interpretation, e.g., ^Z is EOF on MSDOS.
 */

/* Special tokens */
#define EOF_TOKEN	0x01
#define RPN_TOKEN	0x02
#define NL_TOKEN	0x03
#define NOP_TOKEN	0x05
#define FARG_TOKEN	0x06

#define RESERVED1_TOKEN	0x0A	       /* \n */
#define RESERVED2_TOKEN	0x0D	       /* \r */

/* Literal tokens */
#define INT_TOKEN	0x10
#define DOUBLE_TOKEN	0x11
#define CHAR_TOKEN	0x12
#define STRING_TOKEN    0x13
#define COMPLEX_TOKEN	0x14
#define ESC_STRING_TOKEN	0x15
#define RESERVED3_TOKEN	0x1A	       /* ^Z */

/* Tokens that can be LVALUES */
#define IDENT_TOKEN	0x20
#define ARRAY_TOKEN	0x21
#define DOT_TOKEN	0x22
#define IS_LVALUE_TOKEN (((t) <= DOT_TOKEN) && ((t) >= IDENT_TOKEN))

/* do not use these values */
#define RESERVED4_TOKEN	0x23
#define RESERVED5_TOKEN 0x25

/* Flags for struct fields */
#define STATIC_TOKEN	0x26
#define READONLY_TOKEN	0x27

/* Punctuation tokens */
#define OBRACKET_TOKEN	0x2a
#define CBRACKET_TOKEN	0x2b
#define OPAREN_TOKEN	0x2c
#define CPAREN_TOKEN	0x2d
#define OBRACE_TOKEN	0x2e
#define CBRACE_TOKEN	0x2f
#define POUND_TOKEN	0x30
#define COMMA_TOKEN	0x31
#define SEMICOLON_TOKEN	0x32
#define COLON_TOKEN	0x33

/* Operators */
#define POW_TOKEN	 0x38

/* The order of the binary operators must match those in the
 * binary_name_table in sltoken.c
 */
#define FIRST_BINARY_OP	 0x39
#define ADD_TOKEN	 0x39
#define SUB_TOKEN	 0x3a
#define MUL_TOKEN	 0x3b
#define DIV_TOKEN	 0x3c
#define LT_TOKEN	 0x3d
#define LE_TOKEN	 0x3e
#define GT_TOKEN	 0x3f
#define GE_TOKEN	 0x40
#define EQ_TOKEN	 0x41
#define NE_TOKEN	 0x42
#define AND_TOKEN	 0x43
#define OR_TOKEN	 0x44
#define MOD_TOKEN	 0x45
#define BAND_TOKEN	 0x46
#define SHL_TOKEN	 0x47
#define SHR_TOKEN	 0x48
#define BXOR_TOKEN	 0x49
#define BOR_TOKEN	 0x4a
#define LAST_BINARY_OP	 0x4a
#define IS_BINARY_OP(t)	 ((t >= FIRST_BINARY_OP) && (t <= LAST_BINARY_OP))

/* unary tokens -- but not all of them (see grammar) */
#define DEREF_TOKEN	 0x4d
#define NOT_TOKEN	 0x4e
#define BNOT_TOKEN	 0x4f

#define IS_INTERNAL_FUNC(t)	((t >= 0x50) && (t <= 0x56))
#define POP_TOKEN	 0x50
#define CHS_TOKEN	 0x51
#define SIGN_TOKEN	 0x52
#define ABS_TOKEN	 0x53
#define SQR_TOKEN	 0x54
#define MUL2_TOKEN	 0x55
#define EXCH_TOKEN	 0x56

/* Assignment tokens.  Note: these must appear with sequential values.
 * The order here must match the specific lvalue assignments below.
 * These tokens are used by rpn routines in slang.c.  slparse.c maps them
 * onto the specific lvalue tokens while parsing infix.
 * Also the assignment _SLANG_BCST_ assumes this order
 */
#define ASSIGN_TOKEN		0x57
#define PLUSEQS_TOKEN	 	0x58
#define MINUSEQS_TOKEN		0x59
#define PLUSPLUS_TOKEN		0x5A
#define POST_PLUSPLUS_TOKEN	0x5B
#define MINUSMINUS_TOKEN	0x5C
#define POST_MINUSMINUS_TOKEN	0x5D
#define IS_ASSIGNMENT_TOKEN(t)	(((t) >= 0x57) && ((t) <= 0x5D))

/* Directives */
#define IS_BDIRECTIVE_TOKEN(t)	((t >= 0x61) && (t <= 0x73))
#define FIRST_DIRECTIVE_TOKEN	0x61
#define IFNOT_TOKEN	0x61
#define IF_TOKEN	0x62
#define ELSE_TOKEN	0x63
#define FOREVER_TOKEN	0x64
#define WHILE_TOKEN	0x65
#define FOR_TOKEN	0x66
#define _FOR_TOKEN	0x67
#define LOOP_TOKEN	0x68
#define SWITCH_TOKEN	0x69
#define DOWHILE_TOKEN	0x6a
#define ANDELSE_TOKEN	0x6b
#define ORELSE_TOKEN	0x6c
#define ERRBLK_TOKEN	0x6d
#define EXITBLK_TOKEN	0x6e
/* These must be sequential */
#define USRBLK0_TOKEN	0x6f
#define USRBLK1_TOKEN	0x70
#define USRBLK2_TOKEN	0x71
#define USRBLK3_TOKEN	0x72
#define USRBLK4_TOKEN	0x73

#define CONT_TOKEN	0x74
#define BREAK_TOKEN	0x75
#define RETURN_TOKEN	0x76

#define CASE_TOKEN	0x78
#define DEFINE_TOKEN	0x79
#define DO_TOKEN	0x7a
#define VARIABLE_TOKEN	0x7b
#define GVARIABLE_TOKEN	0x7c
#define _REF_TOKEN	0x7d
#define PUSH_TOKEN	0x7e
#define STRUCT_TOKEN	0x7f
#define TYPEDEF_TOKEN	0x80

/* Note: the order here must match the order of the assignment tokens.
 * Also, the first token of each group must be the ?_ASSIGN_TOKEN.
 * slparse.c exploits this order, as well as slang.h.
 */
#define _STRUCT_ASSIGN_TOKEN		0x91
#define _STRUCT_PLUSEQS_TOKEN		0x92
#define _STRUCT_MINUSEQS_TOKEN		0x93
#define _STRUCT_PLUSPLUS_TOKEN		0x94
#define _STRUCT_POST_PLUSPLUS_TOKEN	0x95
#define _STRUCT_MINUSMINUS_TOKEN	0x96
#define _STRUCT_POST_MINUSMINUS_TOKEN	0x97

#define _ARRAY_ASSIGN_TOKEN		0x98
#define _ARRAY_PLUSEQS_TOKEN		0x99
#define _ARRAY_MINUSEQS_TOKEN		0x9A
#define _ARRAY_PLUSPLUS_TOKEN		0x9B
#define _ARRAY_POST_PLUSPLUS_TOKEN	0x9C
#define _ARRAY_MINUSMINUS_TOKEN		0x9D
#define _ARRAY_POST_MINUSMINUS_TOKEN	0x9E

#define _SCALAR_ASSIGN_TOKEN		0x9F
#define _SCALAR_PLUSEQS_TOKEN		0xA0
#define _SCALAR_MINUSEQS_TOKEN		0xA1
#define _SCALAR_PLUSPLUS_TOKEN		0xA2
#define _SCALAR_POST_PLUSPLUS_TOKEN	0xA3
#define _SCALAR_MINUSMINUS_TOKEN	0xA4
#define _SCALAR_POST_MINUSMINUS_TOKEN	0xA5

#define _DEREF_ASSIGN_TOKEN		0xA6

#define _INLINE_ARRAY_TOKEN		0xE0
#define _INLINE_IMPLICIT_ARRAY_TOKEN	0xE1
#define _NULL_TOKEN			0xE2

#define LINE_NUM_TOKEN			0xFC
#define ARG_TOKEN	 		0xFD
#define EARG_TOKEN	 		0xFE
#define NO_OP_LITERAL			0xFF

typedef struct
{
   /* sltoken.c */
   /* SLang_eval_object */
   SLang_Load_Type *llt;
   SLPreprocess_Type *this_slpp;
   /* prep_get_char() */
   char *input_line;
   char cchar;
   /* get_token() */
   int want_nl_token;

   /* slparse.c */
   _SLang_Token_Type ctok;
   int block_depth;
   int assignment_expression;

   /* slang.c : SLcompile() */
   _SLang_Token_Type save_token;
   _SLang_Token_Type next_token;
   void (*slcompile_ptr)(_SLang_Token_Type *);
}
_SLEval_Context;

extern int _SLget_token (_SLang_Token_Type *);
extern void _SLparse_error (char *, _SLang_Token_Type *, int);
extern void _SLparse_start (SLang_Load_Type *);
extern int _SLget_rpn_token (_SLang_Token_Type *);
extern void _SLcompile_byte_compiled (void);

#ifdef HAVE_VSNPRINTF
#define _SLvsnprintf vsnprintf
#else
extern int _SLvsnprintf (char *, unsigned int, char *, va_list);
#endif

#ifdef HAVE_SNPRINTF
#define _SLsnprintf snprintf
#else
extern int _SLsnprintf (char *, unsigned int, char *, ...);
#endif

#endif
