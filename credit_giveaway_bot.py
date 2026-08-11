"""
بوت ديسكورد لتوزيع الكريدت عن طريق ايموجي 🎉
------------------------------------------------
الفكرة:
  1) الأونر (أو صاحب رتبة معيّنة) يفتح "توزيع" بأمر سلاش ويحدد:
       - الحد الأقصى لعدد اللاعبين اللي يقدرون يدخلون
       - عدد الكريدت الكلي اللي بيتوزع
  2) البوت ينزل رسالة (Embed) فيها إيموجي 🎉، وأي عضو يضغط عليه يدخل بالتوزيع.
  3) أول ما يوصل عدد المشاركين للحد الأقصى، يتقفل تلقائيًا ولا يقدر أحد
     جديد يدخل (تفاعله ينشال فورًا).
  4) في زر "🎯 توزيع الكريدت" تحت نفس الرسالة، ما يشتغل إلا لصاحب
     السيرفر/البوت (Owner) أو عضو عنده الرتبة المسموحة. لما يُضغط،
     البوت يوزع الكريدت بالتساوي على كل من دخل ويعلن النتيجة.

المتطلبات:
    pip install -U discord.py

التشغيل:
    python credit_giveaway_bot.py

قبل التشغيل عدّل القيم بالأسفل في قسم الإعدادات (TOKEN و OWNER_ID
و ALLOWED_ROLE_ID اختياري).
"""

import os
import discord
from discord import app_commands
from discord.ext import commands

# ============================ الإعدادات ============================

# التوكن الخاص بالبوت (من Discord Developer Portal)
TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "ضع_التوكن_هنا")

# آيدي المستخدم اللي يعتبر "الأونر" ويقدر يفتح ويوزع بدون رتبة
# اضغط يمين على حسابك بالديسكورد (بعد تفعيل وضع المطور) واختر Copy User ID
OWNER_ID = int(os.environ.get("BOT_OWNER_ID", "0"))

# آيدي رتبة إضافية مسموح لها تفتح/توزع (اختياري) - خليه None لو ما تبي رتبة إضافية
ALLOWED_ROLE_ID = None  # مثال: 123456789012345678

GIVEAWAY_EMOJI = "🎉"

# =====================================================================

intents = discord.Intents.default()
intents.members = True
intents.reactions = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# تخزين حالة كل توزيع نشط بالذاكرة: message_id -> بيانات التوزيع
active_giveaways: dict[int, dict] = {}


def is_authorized(member: discord.Member) -> bool:
    """يتحقق هل الشخص هو الأونر أو عنده الرتبة المسموحة."""
    if member.id == OWNER_ID:
        return True
    if ALLOWED_ROLE_ID is not None:
        role = discord.utils.get(member.roles, id=ALLOWED_ROLE_ID)
        if role is not None:
            return True
    return False


def build_embed(data: dict) -> discord.Embed:
    status = "🔒 اكتمل العدد" if data["locked"] else "🟢 التسجيل مفتوح"
    embed = discord.Embed(
        title="🎉 توزيع كريدت",
        description=(
            f"اضغط على {GIVEAWAY_EMOJI} للمشاركة بالتوزيع!\n\n"
            f"**الحالة:** {status}\n"
            f"**عدد المشاركين:** {len(data['participants'])} / {data['max_participants']}\n"
            f"**إجمالي الكريدت:** {data['credit_amount']}"
        ),
        color=discord.Color.gold() if not data["locked"] else discord.Color.dark_grey(),
    )
    embed.set_footer(text="فتح بواسطة: " + data["opener_name"])
    return embed


class DistributeView(discord.ui.View):
    """زر توزيع الكريدت - ثابت (Persistent) يظل يشتغل حتى بعد إعادة تشغيل البوت."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🎯 توزيع الكريدت",
        style=discord.ButtonStyle.green,
        custom_id="distribute_credit_button",
    )
    async def distribute_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        message_id = interaction.message.id
        data = active_giveaways.get(message_id)

        if data is None:
            await interaction.response.send_message(
                "⚠️ ما لقيت بيانات هذا التوزيع (ممكن يكون خلص أو انحذف).",
                ephemeral=True,
            )
            return

        # تحقق من الصلاحية
        if not isinstance(interaction.user, discord.Member) or not is_authorized(
            interaction.user
        ):
            await interaction.response.send_message(
                "🚫 ما عندك صلاحية تسوي هذا الإجراء. فقط الأونر أو صاحب الرتبة المحددة.",
                ephemeral=True,
            )
            return

        if data["distributed"]:
            await interaction.response.send_message(
                "✅ تم توزيع الكريدت مسبقًا على هذا التوزيع.", ephemeral=True
            )
            return

        participants = list(data["participants"])
        if not participants:
            await interaction.response.send_message(
                "⚠️ ما فيه أي مشارك بعد، لا يمكن التوزيع.", ephemeral=True
            )
            return

        credit_amount = data["credit_amount"]
        share = credit_amount // len(participants)
        remainder = credit_amount % len(participants)

        # نبني النتيجة (نعطي الباقي لأول شخص دخل حتى ما يضيع كريدت)
        results_lines = []
        for i, user_id in enumerate(participants):
            amount = share + (remainder if i == 0 else 0)
            results_lines.append(f"<@{user_id}> — **{amount}** كريدت")

        data["distributed"] = True
        button.disabled = True
        button.label = "✅ تم التوزيع"

        embed = build_embed(data)
        embed.add_field(
            name="نتيجة التوزيع", value="\n".join(results_lines), inline=False
        )

        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send(
            "🎉 تم توزيع الكريدت على المشاركين!\n" + "\n".join(results_lines)
        )


@bot.event
async def on_ready():
    bot.add_view(DistributeView())  # حتى يشتغل الزر حتى لو البوت أعاد التشغيل
    try:
        synced = await bot.tree.sync()
        print(f"تم مزامنة {len(synced)} أمر سلاش.")
    except Exception as e:
        print(f"خطأ بالمزامنة: {e}")
    print(f"البوت شغال باسم {bot.user}")


@bot.tree.command(name="فتح_توزيع", description="افتح توزيع كريدت جديد (للأونر أو الرتبة المسموحة فقط)")
@app_commands.describe(
    الحد_الاقصى="أقصى عدد لاعبين يقدرون يدخلون التوزيع",
    الكريدت="إجمالي عدد الكريدت اللي بيتوزع",
)
async def open_giveaway(
    interaction: discord.Interaction, الحد_الاقصى: int, الكريدت: int
):
    if not isinstance(interaction.user, discord.Member) or not is_authorized(
        interaction.user
    ):
        await interaction.response.send_message(
            "🚫 ما عندك صلاحية تفتح توزيع. فقط الأونر أو صاحب الرتبة المحددة.",
            ephemeral=True,
        )
        return

    if الحد_الاقصى <= 0 or الكريدت <= 0:
        await interaction.response.send_message(
            "⚠️ لازم الحد الأقصى وعدد الكريدت يكونوا أكبر من صفر.", ephemeral=True
        )
        return

    data = {
        "max_participants": الحد_الاقصى,
        "credit_amount": الكريدت,
        "participants": [],  # نستخدم list حتى نحافظ على ترتيب الدخول
        "locked": False,
        "distributed": False,
        "opener_name": interaction.user.display_name,
        "channel_id": interaction.channel_id,
    }

    embed = build_embed(data)
    view = DistributeView()

    await interaction.response.send_message(embed=embed, view=view)
    sent_message = await interaction.original_response()

    active_giveaways[sent_message.id] = data
    await sent_message.add_reaction(GIVEAWAY_EMOJI)


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.user_id == bot.user.id:
        return
    if str(payload.emoji) != GIVEAWAY_EMOJI:
        return

    data = active_giveaways.get(payload.message_id)
    if data is None:
        return

    channel = bot.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)
    member = payload.member or channel.guild.get_member(payload.user_id)

    # لو التوزيع مقفول (اكتمل العدد) أو الشخص مكرر، نشيل تفاعله الجديد
    if data["locked"] or payload.user_id in data["participants"]:
        try:
            await message.remove_reaction(payload.emoji, member)
        except discord.HTTPException:
            pass
        return

    data["participants"].append(payload.user_id)

    if len(data["participants"]) >= data["max_participants"]:
        data["locked"] = True

    embed = build_embed(data)
    await message.edit(embed=embed)


if __name__ == "__main__":
    if TOKEN == "ضع_التوكن_هنا" or not TOKEN:
        print("⚠️ لازم تحط التوكن الصحيح في متغير TOKEN أو بمتغير البيئة DISCORD_BOT_TOKEN")
    else:
        bot.run(TOKEN)
