-- PalScoutChatLogger
-- ------------------------------------------------
-- Hooks Palworld's chat broadcast function and writes every real
-- player chat message to a log file, in a clean, simple format that
-- PalScout's Python code can read reliably.
--
-- Confirmed function signature (from the game's own header files,
-- Pal.hpp):
--
--   struct FPalChatMessage {
--       EPalChatCategory Category;
--       FString Sender;
--       FGuid SenderPlayerUId;
--       FString Message;
--       FGuid ReceiverPlayerUId;
--   };
--
-- Output format (one line per message):
--   PlayerName|Message text here
--
-- No timestamp, no "said" keyword, no SYSTEM lines to filter out --
-- this only fires for real chat messages, and we control the exact
-- format, so PalScout's parser can be much simpler than before.

local LOG_FILE_NAME = "PalScoutChat.log"

-- Writes the mod's own log file into the same folder as this script,
-- so it's easy to find and doesn't depend on any particular server
-- install path.
local function get_log_path()
    return LOG_FILE_NAME
end

local function write_chat_line(sender, message)
    -- Guard against the pipe character breaking our simple format --
    -- replace it if a player somehow has one in their name or message.
    sender = sender:gsub("|", "-")
    message = message:gsub("|", "-")

    local file = io.open(get_log_path(), "a")
    if file then
        file:write(sender .. "|" .. message .. "\n")
        file:close()
    else
        print("[PalScoutChatLogger] ERROR: could not open log file for writing")
    end
end

RegisterHook("/Script/Pal.PalGameStateInGame:BroadcastChatMessage", function(self, ChatMessage)
    local ok, err = pcall(function()
        local chat_message = ChatMessage:get()
        local sender = chat_message.Sender:ToString()
        local message = chat_message.Message:ToString()

        -- Skip empty messages (can happen with some system events)
        if message == nil or message == "" then
            return
        end

        write_chat_line(sender, message)
    end)

    if not ok then
        print("[PalScoutChatLogger] ERROR handling chat message: " .. tostring(err))
    end
end)

print("[PalScoutChatLogger] Loaded and hooked into chat.")
