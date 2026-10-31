//
// C++ Interface: storage_lockers
//
// Description:
//
//
// Author: Gary Dezern <gdezern@xp3000>, (C) 2004
//
// Copyright: See COPYING file that comes with this distribution
//
//
#ifndef __STORAGE_LOCKERS_H__
#define __STORAGE_LOCKERS_H__

#include <string.h>
#include <string>
#include <memory>
#include <vector>
#include "item/item_transfer_command.h"

// Type-specific locker chests only accept matching items.  Containers and
// corpses are rejected by the unsorted chest so they remain visible on the
// locker room floor rather than being hidden inside a sorting chest.
bool locker_eq_type_fits_for_storage(::byte eqType, P_obj obj);
// Ordinary containers pass; private contents require this visit's authenticated opener.
bool locker_container_access_allowed(P_char actor, P_obj container);
bool locker_object_is_private_chest(P_obj object);
void locker_invalidate_chest_access(P_char actor);
void locker_chest_changes_pulse(void);

int guild_locker_room_hook(int room, P_char ch, int cmd, char *arg);
/* The statement that removes every locker grant `name` holds (a character deletion). */
std::string remove_all_locker_access_statement(const char *name);
/* Remove them inside the caller's transaction (a character deletion). */

struct sql_chest_log_entry;
// Reserve the required audit records before moving; abandoned attempts cancel them.
class LockerMovementAudit
{
    public:
	LockerMovementAudit(P_char actor, P_obj source, P_obj target, P_obj item,
			    const char *description = NULL);
	~LockerMovementAudit();
	LockerMovementAudit(const LockerMovementAudit &) = delete;
	LockerMovementAudit &operator=(const LockerMovementAudit &) = delete;
	bool Ready(void) const { return m_ready; }
	void Commit(void);

    private:
	bool m_ready = true;
	std::vector<std::shared_ptr<sql_chest_log_entry>> m_entries;
};

class LockerChest;
class ComboChest;
class PrivateChest;
struct locker_chest_snapshot;

class StorageLocker
{
    public:
	StorageLocker(int rroom, P_char chLocker, P_char chUser);
	~StorageLocker(void);

	// basically, deletes everything IN the list without deleting the list
	//  object itself.
	void NukeLockerChests(void);

	// parses 'args' and creates needed chests
	bool MakeChests(P_char ch, char *args);

	// figures out where 'obj' belongs and puts it there.  If
	//  it doesn't belong anyplace, return false;
	bool PutInProperChest(P_obj obj);

	P_char GetLockerChar(void) { return m_chLocker; };
	P_char GetLockerUser(void) { return m_chUser; };
	bool LockerUserIsOwner(void) const { return m_userIsOwner; }
	bool LockerUserMatches(P_char ch) const
	{
		return ch && ch == m_chUser && ch->runtime_id == m_userRuntimeId;
	}

	bool ChestWritePending(void) const { return m_chestWritePending; }
	void SetChestWritePending(bool pending)
	{
		m_chestWritePending = pending;
		InvalidateChestAccess();
	}
	uint64_t VisitId(void) const { return m_chLocker ? m_chLocker->runtime_id : 0; }
	bool PrivateContentsDurable(void);
	bool LockerToPFile(void);
	void PFileToLocker(void);
	void SortIValues(void);
	LockerChest *FindChestForObject(P_obj obj);

	static void event_resortLocker(P_char chLocker, P_char ch, P_obj obj, void *data);
	static void event_savePrivateChests(P_char chLocker, P_char ch, P_obj obj, void *data);
	bool SchedulePrivateSave(void);
	int m_itemCount;

	int GetCurrentChestId(void) { return m_currentChestId; };
	void SetCurrentChestId(int id, bool manager = false)
	{
		m_currentChestId = id;
		m_currentChestManager = manager;
	};
	bool CurrentChestOpenedAsManager(void) const { return m_currentChestManager; }
	uint64_t GetChestAccessGeneration(void) const { return m_chestAccessGeneration; }
	void InvalidateChestAccess(void)
	{
		m_currentChestId = 0;
		m_currentChestManager = false;
		++m_chestAccessGeneration;
	}
	int GetLockerId(void) { return m_lockerId; };
	void SetLockerId(int id) { m_lockerId = id; };
	int GetPublicChestId(void) { return m_publicChestId; };
	void SetPublicChestId(int id) { m_publicChestId = id; };
	void AddPrivateChest(LockerChest *chest) { AddLockerChest(chest); };
	// The private chest named `name` (any case), or NULL.
	PrivateChest *FindPrivateChest(const char *name);
	std::vector<PrivateChest *> GetPrivateChests(void);
	// Unlink the chest and delete it.
	void RemovePrivateChest(PrivateChest *chest);
	int GetRealRoom(void) { return m_realRoom; };

    protected:
	LockerChest *AddLockerChest(LockerChest *p);
	LockerChest *m_pChestList;
	int m_realRoom;
	P_char m_chLocker;
	P_char m_chUser;
	uint64_t m_userRuntimeId;
	// The authenticated entry verdict outlives the user's descriptor.
	bool m_userIsOwner;
	//  int m_itemCount;
	bool m_bIValue;
	int m_currentChestId;
	bool m_currentChestManager;
	uint64_t m_chestAccessGeneration;
	int m_lockerId;
	int m_publicChestId;
	bool m_chestWritePending = false;
};

class LockerChest
{
	friend class StorageLocker;
	friend class ComboChest;

    public:
	// destructor...  should drop all contents of check into room,
	//   remove check_obj from room, and extract check_obj.
	virtual ~LockerChest(void);

	// returns the chest object assoicated with this c++ class
	virtual P_obj GetChestObj(void) { return m_pChestObject; };

	// does an object fit in 'this' locker?
	virtual bool ItemFits(P_obj /*obj*/) { return true; };

	virtual bool IsPrivateChest(void) { return false; };
	virtual int GetChestId(void) { return 0; };

	virtual void FillExtraDescBuf(char *GBuf1);

	// LATENT: no destDesc size parameter — safe only because keywords are
	// fixed non-empty strings. Would need a size_t param to harden.
	void BeautifyDesc(const char *srcDesc, char *destDesc);

	const char *m_chestKeyword;
	const char *m_chestDescText;

	static const unsigned m_chestVnum;

    protected:
	LockerChest(const char *keyword, const char *prettyDesc)
		: m_chestKeyword(keyword)
		, m_chestDescText(prettyDesc)
		, m_pNextInChain(NULL)
		, m_pChestObject(NULL){};

	P_obj CreateChestObject(void);

	LockerChest *m_pNextInChain; // init to 0
	P_obj m_pChestObject; // init to 0

	static const char *m_keywords;
	static const char *m_PrettyDesc;

    private:
};

class UnsortedChest : public LockerChest
{
	friend class StorageLocker;

    public:
	virtual bool ItemFits(P_obj obj)
	{
		return ((obj->type == ITEM_CONTAINER) || (obj->type == ITEM_CORPSE)) ? false : true;
	};

    protected:
	UnsortedChest(void)
		: LockerChest("unsorted", "that are unsorted"){};
};

class EqSlotChest : public LockerChest
{
	friend class StorageLocker;

    public:
	virtual bool ItemFits(P_obj obj)
	{
		if (!obj || obj->type == ITEM_CONTAINER || obj->type == ITEM_CORPSE)
			return false;
		return (obj->wear_flags & m_eqBit) ? true : false;
	};

    protected:
	EqSlotChest(unsigned int eqSlotBit, const char *keyword, const char *prettyDesc)
		: LockerChest(keyword, prettyDesc)
		, m_eqBit(eqSlotBit){};

    private:
	unsigned int m_eqBit;
};

class EqWearChest : public LockerChest
{
	friend class StorageLocker;

    public:
	virtual bool ItemFits(P_obj obj)
	{
		if (!obj || obj->type == ITEM_CONTAINER || obj->type == ITEM_CORPSE)
			return false;
		return IS_SET(obj->extra_flags, ITEM_ALLOWED_CLASSES) ?
			       IS_SET(obj->anti_flags, m_wearClass) :
			       !IS_SET(obj->anti_flags, m_wearClass);
	};

    protected:
	EqWearChest(unsigned wearClass, const char *keyword, const char *prettyDesc)
		: LockerChest(keyword, prettyDesc)
		, m_wearClass(wearClass){};

    private:
	unsigned m_wearClass;
};

class EqTypeChest : public LockerChest
{
	friend class StorageLocker;

    public:
	virtual bool ItemFits(P_obj obj) { return locker_eq_type_fits_for_storage(m_eqType, obj); };

    protected:
	EqTypeChest(::byte eqType, const char *keyword, const char *prettyDesc)
		: LockerChest(keyword, prettyDesc)
		, m_eqType(eqType){};

    private:
	::byte m_eqType;
};

class EqApplyChest : public LockerChest
{
	friend class StorageLocker;

    public:
	virtual bool ItemFits(P_obj obj);

    protected:
	EqApplyChest(::byte applyType, const char *keyword, const char *prettyDesc)
		: LockerChest(keyword, prettyDesc)
		, m_applyType(applyType){};

    private:
	::byte m_applyType;
};

class EqAffectChest : public LockerChest
{
	friend class StorageLocker;

    public:
	virtual bool ItemFits(P_obj obj);

    protected:
	EqAffectChest(int b, int bv, const char *keyword, const char *prettyDesc)
		: LockerChest(keyword, prettyDesc)
		, m_bitVector(bv)
		, m_bit(b){};

    private:
	int m_bitVector;
	int m_bit;
};

class OreChest : public LockerChest
{
	friend class StorageLocker;

    public:
	virtual bool ItemFits(P_obj obj)
	{
		if (!obj || obj->type == ITEM_CONTAINER || obj->type == ITEM_CORPSE)
			return false;
		return (strstr(obj->name, "_ore_") &&
			(!m_oreType[0] || strstr(obj->name, m_oreType))) ?
			       true :
			       false;
	};

    protected:
	OreChest(const char *oreType, const char *keyword, const char *prettyDesc)
		: LockerChest(keyword, prettyDesc)
	{
		if (oreType && oreType[0])
			strcpy(m_oreType, oreType);
		else
			m_oreType[0] = '\0';
	};

    private:
	char m_oreType[1024];
};

class ComboChest : public LockerChest
{
	friend class StorageLocker;

    public:
	virtual bool ItemFits(P_obj obj);

	virtual void FillExtraDescBuf(char *GBuf1);

    protected:
	ComboChest(LockerChest *pChestList)
		: LockerChest("custom", "that you custom specified")
		, m_LockerChests(pChestList){};
	~ComboChest(void);

	LockerChest *m_LockerChests;
};

class PrivateChest : public LockerChest
{
	friend class StorageLocker;

    public:
	// password_hash is the stored bcrypt hash, or NULL for none.
	PrivateChest(int chest_id, const char *name, const char *password_hash);

	virtual bool ItemFits(P_obj /*obj*/) override { return false; };
	virtual bool IsPrivateChest(void) override { return true; };
	virtual int GetChestId(void) override { return m_chestId; };
	const char *GetName(void) { return m_chestName; };
	// Memory holds the chest's password: empty for none.
	const std::string &GetPasswordHash(void) { return m_passwordHash; };
	void SetPasswordHash(const char *hash);
	bool SaveContents(StorageLocker *locker, bool durable);
	// Submit/acknowledge retained captures; true while work remains.
	bool FlushContents(void);

    protected:
	int m_chestId;
	std::string m_passwordHash;
	char m_chestName[128];
	std::shared_ptr<struct sql_write_receipt> m_saveReceipt;
	std::vector<uint8_t> m_pendingContents;
	std::vector<uint8_t> m_savedContents;
	std::shared_ptr<const locker_chest_snapshot> m_pendingSnapshot;
	std::shared_ptr<const locker_chest_snapshot> m_nextSnapshot;
	std::vector<uint8_t> m_nextContents;
};

#endif // __STORAGE_LOCKERS_H__
