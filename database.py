import aiosqlite
import random

from collections import defaultdict


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: aiosqlite.Connection | None = None

    async def connect(self):
        # Starts the connection to the DB
        self.conn = await aiosqlite.connect(self.db_path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.execute("PRAGMA foreign_keys = ON;")
        await self.conn.commit()

    async def close(self):
        # Closes the connection to DB when the client is shutdown
        if self.conn:
            await self.conn.close()

    async def add_squad_member(self, owner, squad, role, player, nickname):
        current_game = await self.get_newst_game()
        # Check so match number of players not reached
        player_id = await self.find_user(user=player, nickname=nickname)
        already_signedup = await self.check_if_already_signedup(player_id=player_id)
        if already_signedup:
            return "Player already signed up"
        total_players = await self.check_if_max_signup_reached(current_game)
        if total_players:
            return "Maximum players Reached"
        #  Check so that who signed up has a squad
        owner_id = await self.find_user(user=owner)
        squad_id = await self.get_squad_id(owner_id=owner_id, game_id=current_game)

        # Check so squad is not full
        squad_memebrs = await self.check_if_squad_is_full(
            squad_id=squad_id, squad_type=squad
        )
        if squad_memebrs:
            return "Your squad is full"
        # Chek so signup to right Role Should not be needing this..
        # answer = await self.check_if_right_role(squad=squad, squad_id=squad_id)
        # if not answer:
        #     return "Select Role according to your Squad Type"

        role_id = await self.get_role_id(role=role)
        answer = await self.add_squad_member_to_db(
            squad_id=squad_id, player_id=player_id, role_id=role_id
        )
        if answer:
            if isinstance(player, int):
                player = f"<@{player}>"
            return f"You signed up {player} as `{role}` in `{squad}` squad!"
        else:
            return "Something went wrong. I blame Jeuse"

    async def create_squad(self, user, squad, name, nickname):

        # Get active game
        game = await self.get_newst_game()
        # Check if Owner is already signed up and is in database if not in database add.
        player_id = await self.find_user(user=user, nickname=nickname)
        signed_up = await self.check_if_already_signedup(player_id)
        if signed_up:
            # Return Message player already signedup
            return "User already signed up"

        # Check if still space and what side has lowest number squad of said type / lowest number player
        answer = await self.select_side(
            game_id=game, squad=squad, name=name, owner_id=player_id
        )

        return answer

    async def find_user(self, user, nickname: str | None = None):
        if nickname is None:
            nickname = user
        # Checks what type has been added. Discord ID or just Name
        if isinstance(user, int):
            # Discord ID input
            query = "SELECT player_id FROM players WHERE discord_id = ?"
            params = (user,)
            insert_query = (
                "INSERT INTO players (discord_id, player_nickname) VALUES (?, ?)"
            )
            insert_params = (user, nickname)

        elif isinstance(user, str):
            # Name input
            query = "SELECT player_id FROM players WHERE player_name = ?"
            params = (user,)
            insert_query = (
                "INSERT INTO players (player_name, player_nickname) VALUES (?, ?)"
            )
            insert_params = (user, nickname)

        else:
            # Something not correct added
            raise ValueError("user must be int (discord_id) or str (player_name)")

        # Look for existing record
        async with self.conn.execute(query, params) as cursor:
            row = await cursor.fetchone()

        if row:
            return row[0]

        # Not found → insert new
        async with self.conn.execute(insert_query, insert_params) as cursor:
            await self.conn.commit()
            return cursor.lastrowid

    async def check_if_right_role(self, squad, squad_id):
        # Check that the role is correct.
        # This function is obselete. The View function dont premit ppl to
        # add wrong roles
        query = "SELECT type_id FROM squads WHERE squad_id = ?"
        match squad:
            case "Commander":
                type_id = 1
            case "Infantry":
                type_id = 2
            case "Logistic":
                type_id = 3
            case "Armor":
                type_id = 4
        async with self.conn.execute(query, (squad_id,)) as cursor:
            answer = await cursor.fetchone()
        if answer[0] == type_id:
            return True
        else:
            return False

    async def check_if_already_signedup(self, player_id):
        # get newsest game:
        active_game = await self.get_newst_game()

        query = """
                SELECT 1
                FROM squad_assignments sa
                JOIN squads s ON sa.squad_id = s.squad_id
                WHERE s.game_id = ?
                AND sa.player_id = ?;
                """
        async with self.conn.execute(query, (active_game, player_id)) as cursor:
            squad = await cursor.fetchone()

        return squad is not None

    async def check_if_max_signup_reached(self, game_id):
        # count how many is signed up and stops it at 100
        query = "SELECT count(player_id) FROM squad_assignments WHERE squad_id IN (SELECT squad_id FROM squads WHERE game_id = ?)"
        async with self.conn.execute(query, (game_id,)) as cursor:
            row = await cursor.fetchone()
        total_players = row[0]
        print(total_players)
        if total_players <= 100:
            return False
        else:
            return True

    async def check_if_squad_is_full(self, squad_id, squad_type):
        # Controll check if the squad is full and cant handle any more members
        query = "SELECT count(player_id) FROM squad_assignments WHERE squad_id = ?"
        async with self.conn.execute(query, (squad_id,)) as cursor:
            row = await cursor.fetchone()
        squad_members = row[0]
        squad_max = {"Commander": 2, "Infantry": 20, "Logistic": 4, "Armor": 4}
        print(squad_members)
        if squad_members < squad_max[squad_type]:
            return False
        else:
            return True

    async def select_side(self, game_id, squad, name, owner_id):
        # Sort out Squad Type and Leader role.
        # This function randomiser and palce squads on appropriet
        # Sides depending on player ammount and squad types
        match squad:
            case "Commander":
                type_id = 1
                role = "Commander"
            case "Infantry":
                type_id = 2
                role = "NCO"
            case "Logistic":
                type_id = 3
                role = "NCO"
            case "Armor":
                type_id = 4
                role = "Tank Commander"

        # Find out what side to join
        # PROBABLY NEED SOME IMPORVMENTS WHEN I GOT SOME DATA IN
        query = """
                WITH sides AS (
                    SELECT 1 AS side_id
                    UNION ALL
                    SELECT 2 AS side_id
                )
                SELECT 
                    s.side_id,
                    COUNT(sa.player_id) AS Players,
                    SUM(CASE WHEN sq.type_id = 1 THEN 1 ELSE 0 END) AS Commander,
                    SUM(CASE WHEN sq.type_id = 2 THEN 1 ELSE 0 END) AS Infantry,
                    SUM(CASE WHEN sq.type_id = 3 THEN 1 ELSE 0 END) AS Logistic,
                    SUM(CASE WHEN sq.type_id = 4 THEN 1 ELSE 0 END) AS Armor
                FROM sides s
                LEFT JOIN squads sq ON s.side_id = sq.side_id AND sq.game_id = ?
                LEFT JOIN squad_assignments sa ON sq.squad_id = sa.squad_id
                GROUP BY s.side_id
                ORDER BY s.side_id ASC;
                """
        async with self.conn.execute(query, (game_id,)) as cursor:
            row = await cursor.fetchall()
        if row:
            result = [dict(r) for r in row]
            total_players = result[0]["Players"] + result[1]["Players"]
            if total_players >= 100:
                return "Maximum amount of players Reached"
            # Set limits to MAX per side
            limits = {
                "Commander": 1,
                "Infantry": float("inf"),  # unlimited
                "Logistic": 1,
                "Armor": 2,
            }
            if squad == "Infantry":
                # Always pick side with fewer players
                allies, axis = result
                if allies["Players"] < axis["Players"]:
                    side_id = 1
                elif axis["Players"] < allies["Players"]:
                    side_id = 2
                else:
                    # If equal → randomize
                    side_id = random.randint(1, 2)
            else:
                available_sides = []
                for side in result:
                    if side[squad] < limits[squad]:
                        available_sides.append(side["side_id"])
                # IF no available spots
                if not available_sides:
                    return f"No available slots for {squad}"
                if len(available_sides) == 1:
                    side_id = available_sides[0]
                else:
                    side_id = random.randint(1, 2)

        else:
            side_id = random.randint(1, 2)
            print(side_id)

        # SEPERATE THIS PART?
        # CREATE SQUAD;
        query = "INSERT INTO squads (owner_id, game_id, side_id, type_id, squad_name) VALUES (?,?,?,?,?)"
        conditions = (owner_id, game_id, side_id, type_id, name)
        await self.conn.execute(query, conditions)
        await self.conn.commit()
        # ADD OWNER TO SQUAD LIST
        # Get Squad id
        squad_id = await self.get_squad_id(owner_id=owner_id, game_id=game_id)
        role_id = await self.get_role_id(role)
        added_owner = await self.add_squad_member_to_db(
            squad_id=squad_id, player_id=owner_id, role_id=role_id
        )
        if added_owner:
            return "Squad has been added to system"
        else:
            return "There was an Error in enlistment proccess"

    async def add_game(self, date, title, description):
        # Adds a game to the current playlist same as starting a new game
        query = "INSERT INTO games (game_date, title, description) VALUES (?, ?, ?)"
        try:
            await self.conn.execute(query, (date, title, description))
            await self.conn.commit()
            return True
        except:
            return False

    async def get_game_data(self):
        # collects the game data for the squad composition
        query = """
            SELECT game_id, game_date, title, description
            FROM games
            ORDER BY game_id DESC
            LIMIT 1
        """
        async with self.conn.execute(query) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None  # no games in DB

        # row = (game_id, game_date, title, description)
        return {
            "game_id": row[0],
            "game_date": row[1],
            "title": row[2],
            "description": row[3],
        }

    async def get_squad_id(self, owner_id, game_id):
        # Returns the squad id of the owner on current acctive game
        query = "SELECT squad_id FROM squads WHERE owner_id = ? AND game_id = ?"
        async with self.conn.execute(query, (owner_id, game_id)) as cursor:
            row = await cursor.fetchone()
        squad_id = row[0]
        return squad_id

    async def get_role_id(self, role):
        # Returns the ID of role
        query = "SELECT role_id FROM roles WHERE role_name = ?"
        async with self.conn.execute(query, (role,)) as cursor:
            row = await cursor.fetchone()
        role_id = row[0]
        return role_id

    async def add_squad_member_to_db(self, squad_id, player_id, role_id):
        # Insert a member to the selected squad (make a function to check so max is not reached)
        query = "INSERT INTO squad_assignments (squad_id, player_id,role_id) VALUES (?, ?, ?)"
        try:
            await self.conn.execute(query, (squad_id, player_id, role_id))
            await self.conn.commit()
            return True
        except:
            return False

    async def get_newst_game(self):
        # Collect the game id of the active game
        query = "SELECT game_id FROM games ORDER BY game_id DESC LIMIT 0, 1"
        async with self.conn.execute(query) as cursor:
            row = await cursor.fetchone()
        game_id = row[0]
        return game_id

    async def save_channel_data(
        self, guild_id, category_id, channel_id, message_id, type
    ):
        # Saves the channel data of selected channels
        query = """
        INSERT INTO channel_manager (guild, type, category, channel, message)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(guild, type) DO UPDATE SET
        channel = excluded.channel,
        category = excluded.category,
        message = excluded.message"""
        await self.conn.execute(
            query, (guild_id, type, category_id, channel_id, message_id)
        )
        await self.conn.commit()

    async def find_channel_data(self, guild, type):
        # Find the channel data
        query = """
                SELECT category as category, channel as channel, message as message FROM channel_manager WHERE guild = ? AND type = ?
                """

        async with self.conn.execute(query, (guild, type)) as cursor:
            row = await cursor.fetchall()

        print(row)
        if row:
            result = [dict(r) for r in row]

        return result

    async def get_squad_data(self, guild_id):
        # Get all data for signed up squads and members.
        query = """
                SELECT 
                s.side_name,
                st.type_name AS squad_type,
                sq.squad_name,
                p.player_id,
                p.player_name,
                p.discord_id,
                r.role_name,
                f.thread_id,
                f.message_id
                FROM squad_assignments sa
                JOIN squads sq      ON sa.squad_id = sq.squad_id
                JOIN players p      ON sa.player_id = p.player_id
                JOIN roles r        ON sa.role_id = r.role_id
                JOIN sides s        ON sq.side_id = s.side_id
                JOIN squad_types st ON sq.type_id = st.type_id
                LEFT JOIN forum_posts f ON f.player_id = p.player_id
                WHERE sq.game_id = ?
                ORDER BY s.side_name, st.type_name, sq.squad_name;
                """
        game_id = await self.get_newst_game()
        async with self.conn.execute(query, (game_id,)) as cursor:
            rows = await cursor.fetchall()
        data = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))

        for (
            side,
            squad_type,
            squad_name,
            player_id,
            player_name,
            discord_id,
            role_name,
            thread_id,
            message_id,
        ) in rows:
            # Always use mention if available
            if discord_id:
                display = f"<@{discord_id}>"
            else:
                display = player_name

            # Add role
            display += f" – {role_name}"

            # Add service record link if available
            if thread_id and message_id:
                url = (
                    f"https://discord.com/channels/{guild_id}/{thread_id}/{message_id}"
                )
                display += f" [📜]({url})"

            data[side][squad_type][squad_name][display] = role_name
        return data

    async def get_squad_type(self, owner):
        # Check what type of squad the owner has
        current_game = await self.get_newst_game()
        player_id = await self.find_user(user=owner)
        squad_id = await self.get_squad_id(owner_id=player_id, game_id=current_game)

        query = """        
                SELECT st.type_name
                FROM squads s
                JOIN squad_types st ON s.type_id = st.type_id
                WHERE s.squad_id = ?;
                """
        async with self.conn.execute(query, (squad_id,)) as cursor:
            row = await cursor.fetchone()

        if row:
            type_name = row[0]
            return type_name
        else:
            return None

    async def get_squad_members(self, owner):
        # Get the members of the squad
        current_game = await self.get_newst_game()
        player_id = await self.find_user(user=owner)
        squad_id = await self.get_squad_id(owner_id=player_id, game_id=current_game)

        query = """        
            SELECT p.player_id, p.player_nickname, r.role_name
            FROM squad_assignments sa
            JOIN players p ON p.player_id = sa.player_id
            JOIN roles r ON r.role_id = sa.role_id
            WHERE sa.squad_id = ?;
        """
        async with self.conn.execute(query, (squad_id,)) as cursor:
            rows = await cursor.fetchall()

        return rows

    async def get_player_name(self, player_id):
        # Get the name of selected player_id
        query = "SELECT player_nickname FROM players WHERE player_id = ?"
        async with self.conn.execute(query, (player_id)) as cursor:
            row = await cursor.fetchone()
        player_name = row[0]
        return player_name

    async def edit_squad_member(self, owner: int, player_id: str, new_role: str):
        # Change the role of selected member in owners squad
        role_id = await self.get_role_id(role=new_role)
        owner_id = await self.find_user(user=owner)
        game_id = await self.get_newst_game()
        squad_id = await self.get_squad_id(owner_id=owner_id, game_id=game_id)
        query = """
            UPDATE squad_assignments
            SET role_id = ?
            WHERE squad_id = ? AND player_id = ?
        """
        await self.conn.execute(query, (role_id, squad_id, player_id))
        await self.conn.commit()
        player_name = await self.get_player_name(player_id)
        return f"✅ Updated role for {player_name} to {new_role}"

    async def remove_squad_member(self, owner: int, player_id: str):
        # Removes selected member out of owners squad
        owner_id = await self.find_user(user=owner)
        game_id = await self.get_newst_game()
        squad_id = await self.get_squad_id(owner_id=owner_id, game_id=game_id)
        query = """
            DELETE FROM squad_assignments
            WHERE squad_id = ? AND player_id = ?
        """
        await self.conn.execute(query, (squad_id, player_id))
        await self.conn.commit()
        player_name = await self.get_player_name(player_id)
        return f"❌ Removed {player_name} from your squad."

    async def check_if_has_squad(self, user):
        # Great english but checks if user has a squad
        current_game = await self.get_newst_game()
        player_id = await self.find_user(user=user)

        query = """
            SELECT squad_id
            FROM squads
            WHERE owner_id = ? AND game_id = ?
            LIMIT 1;
        """
        async with self.conn.execute(query, (player_id, current_game)) as cursor:
            row = await cursor.fetchone()

        return row is not None

    async def get_times(self):
        # Probably going to be a change here to also select the guild ID that
        # that will be added in to this
        query = "SELECT time_str FROM schedules"

        async with self.conn.execute(query) as cursor:
            results = [row[0] for row in await cursor.fetchall()]

        return results

    async def get_active_players(self):
        # Get all the active players to run service record update
        query = """
                SELECT p.player_id, f.message_id, f.thread_id, p.player_nickname
                FROM squads s
                JOIN squad_assignments sa ON s.squad_id = sa.squad_id
                JOIN players p ON sa.player_id = p.player_id
                LEFT JOIN forum_posts f ON f.player_id = p.player_id
                WHERE s.game_id = ?;
                """
        active_game = await self.get_newst_game()

        async with self.conn.execute(query, (active_game,)) as cursor:
            results = await cursor.fetchall()
        return results

    async def save_player_thread(self, player_id, thread_id, message_id):
        # Save the thread ID of player to played data
        query = (
            "INSERT INTO forum_posts(player_id, thread_id, message_id) VALUES (?, ?, ?)"
        )
        async with self.conn.execute(
            query, (player_id, thread_id, message_id)
        ) as cursor:
            await self.conn.commit()

    async def games_played(self, player_id):
        # Count how many games player has played
        query = """
                SELECT COUNT(DISTINCT s.game_id)
                FROM squad_assignments sa
                JOIN squads s ON sa.squad_id = s.squad_id
                WHERE sa.player_id = ?
                """
        async with self.conn.execute(query, (player_id,)) as cursor:
            results = await cursor.fetchone()
        return results[0]

    async def squads_played(self, player_id):
        # check how many times he played what type of squad
        query = """
                SELECT st.type_name, COUNT(*) 
                FROM squad_assignments sa
                JOIN squads s ON sa.squad_id = s.squad_id
                JOIN squad_types st ON s.type_id = st.type_id
                WHERE sa.player_id = ?
                GROUP BY st.type_name
                """
        async with self.conn.execute(query, (player_id,)) as cursor:
            results = await cursor.fetchall()
        return results

    async def roles_played(self, player_id):
        # Check what Roles the player has played
        query = """
                SELECT r.role_name, COUNT(*) 
                FROM squad_assignments sa
                JOIN roles r ON sa.role_id = r.role_id
                WHERE sa.player_id = ?
                GROUP BY r.role_name
                """
        async with self.conn.execute(query, (player_id,)) as cursor:
            results = await cursor.fetchall()
        return results

    async def sides_played(self, player_id):
        # Check what side the player has played the most
        query = """
                SELECT si.side_name, COUNT(*) 
                FROM squad_assignments sa
                JOIN squads s ON sa.squad_id = s.squad_id
                JOIN sides si ON s.side_id = si.side_id
                WHERE sa.player_id = ?
                GROUP BY si.side_name
                """
        async with self.conn.execute(query, (player_id,)) as cursor:
            results = await cursor.fetchall()
        return results

    async def remove_squad_and_members(self, owner_id: int) -> str:
        # Completley remove owners squad
        player_id = await self.find_user(user=owner_id)

        async with self.conn.execute(
            "SELECT squad_id FROM squads WHERE owner_id = ?", (player_id,)
        ) as cursor:
            squad = await cursor.fetchone()

        if not squad:
            return "No squad found to remove."

        squad_id = squad[0]

        await self.conn.execute(
            "DELETE FROM squad_assignments WHERE squad_id = ?", (squad_id,)
        )
        await self.conn.execute("DELETE FROM squads WHERE squad_id = ?", (squad_id,))
        await self.conn.commit()

        return f"Squad {squad_id} and all its members have been removed."
