#ifndef DURIS_SQL_ITEM_OWNER_ROWS_H
#define DURIS_SQL_ITEM_OWNER_ROWS_H

/* The item_current_owner columns an owner check reads, joined as `current_item` with
 * item_owner_revision as `owner`; a read elsewhere selects them in this order. */
#define SQL_ITEM_OWNER_COLUMNS                                                         \
	"current_item.root_item_uid,COALESCE(current_item.parent_item_uid,0),"         \
	"current_item.owner_type,current_item.owner_id,current_item.owner_context_id," \
	"current_item.item_revision,current_item.vnum,current_item.state,owner.revision"
#define SQL_ITEM_OWNER_REVISION_JOIN                                                       \
	"LEFT JOIN item_owner_revision owner ON owner.owner_type=current_item.owner_type " \
	"AND owner.owner_id=current_item.owner_id "                                        \
	"AND owner.owner_context_id=current_item.owner_context_id"
#define SQL_ITEM_OWNER_SELECT            \
	"SELECT " SQL_ITEM_OWNER_COLUMNS \
	" FROM item_current_owner current_item " SQL_ITEM_OWNER_REVISION_JOIN
/* The same check for those columns already read (row[0..8], or NULL when the item
 * has no ownership row). */
bool sql_persistence_item_owner_fields_match(unsigned long long item_uid, const char *owner_type,
					     unsigned long long expected_id,
					     unsigned long long expected_context_id,
					     const char *const *row);

#endif
