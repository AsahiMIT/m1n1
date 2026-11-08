/* SPDX-License-Identifier: MIT */

#include "adt.h"
#include "asc.h"
#include "malloc.h"
#include "string.h"
#include "utils.h"

#define ASC_CPU_CONTROL       0x44
#define ASC_CPU_CONTROL_START 0x10

#define ASC_MBOX_CONTROL_FULL  BIT(16)
#define ASC_MBOX_CONTROL_EMPTY BIT(17)

#define ASC_MBOX_A2I_CONTROL 0x110
#define ASC_MBOX_A2I_SEND0   0x800
#define ASC_MBOX_A2I_SEND1   0x808
#define ASC_MBOX_A2I_RECV0   0x810
#define ASC_MBOX_A2I_RECV1   0x818

#define ASC_MBOX_I2A_CONTROL 0x114
#define ASC_MBOX_I2A_SEND0   0x820
#define ASC_MBOX_I2A_SEND1   0x828
#define ASC_MBOX_I2A_RECV0   0x830
#define ASC_MBOX_I2A_RECV1   0x838

#define ASC_MSGBOX_ALIAS_OFFSET 0x10000
#define ASC_MSGBOX_STRIDE       0x80
#define ASC_MSGBOX_RECV         0x00
#define ASC_MSGBOX_SEND         0x10
#define ASC_MSGBOX_STATUS       0x20
#define ASC_MSGBOX_RX           GENMASK(3, 0)
#define ASC_MSGBOX_TX           GENMASK(11, 8)

struct asc_dev {
    uintptr_t cpu_base;
    uintptr_t base;
    int iop_node;
    bool messagebox;
};

static bool asc_get_bool(int node, const char *name)
{
    u32 size;
    const void *value = adt_getprop(adt, node, name, &size);
    return value && ((size == sizeof(u32) && *(const u32 *)value) ||
                     (size == 5 && !memcmp(value, "true", 5)));
}

asc_dev_t *asc_init(const char *path)
{
    int asc_path[8];
    int node = adt_path_offset_trace(adt, path, asc_path);
    if (node < 0) {
        printf("asc: Error getting ASC node %s\n", path);
        return NULL;
    }

    u64 base;
    if (adt_get_reg(adt, asc_path, "reg", 0, &base, NULL) < 0) {
        printf("asc: Error getting ASC %s base address.\n", path);
        return NULL;
    }

    asc_dev_t *asc = calloc(1, sizeof(*asc));
    if (!asc)
        return NULL;

    asc->iop_node = adt_first_child_offset(adt, node);
    asc->cpu_base = base;
    asc->base = base + 0x8000;

    if (adt_is_compatible(adt, node, "iop,ascwrap-v8")) {
        u32 mailbox = 0;
        u64 msgbox_base, size;
        int mailbox_ret = ADT_GETPROP(adt, node, "msgbox-mailbox-num", &mailbox);
        u64 aperture = 2 * (u64)mailbox + !asc_get_bool(node, "msgbox-using-postoffice");
        u64 offset = aperture * ASC_MSGBOX_STRIDE;
        if (!asc_get_bool(node, "msgbox-using-alias"))
            offset += ASC_MSGBOX_ALIAS_OFFSET;
        if ((mailbox_ret < 0 && adt_get_property(adt, node, "msgbox-mailbox-num")) ||
            adt_get_reg(adt, asc_path, "reg", 2, &msgbox_base, &size) < 0 ||
            offset + ASC_MSGBOX_STRIDE > size) {
            printf("asc: Invalid messagebox aperture for %s\n", path);
            free(asc);
            return NULL;
        }
        asc->messagebox = true;
        asc->base = msgbox_base + offset;
    }

    // clear32(base + ASC_CPU_CONTROL, ASC_CPU_CONTROL_START);
    return asc;
}

void asc_free(asc_dev_t *asc)
{
    free(asc);
}

int asc_get_iop_node(asc_dev_t *asc)
{
    return asc->iop_node;
}

void asc_cpu_start(asc_dev_t *asc)
{
    set32(asc->cpu_base + ASC_CPU_CONTROL, ASC_CPU_CONTROL_START);
}

void asc_cpu_stop(asc_dev_t *asc)
{
    clear32(asc->cpu_base + ASC_CPU_CONTROL, ASC_CPU_CONTROL_START);
}

bool asc_cpu_running(asc_dev_t *asc)
{
    return read32(asc->cpu_base + ASC_CPU_CONTROL) & ASC_CPU_CONTROL_START;
}

bool asc_can_recv(asc_dev_t *asc)
{
    if (asc->messagebox)
        return read32(asc->base + ASC_MSGBOX_STATUS) & ASC_MSGBOX_RX;
    return !(read32(asc->base + ASC_MBOX_I2A_CONTROL) & ASC_MBOX_CONTROL_EMPTY);
}

bool asc_recv(asc_dev_t *asc, struct asc_message *msg)
{
    if (!asc_can_recv(asc))
        return false;

    if (asc->messagebox) {
        u64 base = asc->base + ASC_MSGBOX_RECV;
        msg->msg0 = read32(base);
        msg->msg0 |= (u64)read32(base + 4) << 32;
        msg->msg1 = read32(base + 8);
        /* Reading the fourth word pops the receive FIFO. */
        read32(base + 12);
    } else {
        msg->msg0 = read64(asc->base + ASC_MBOX_I2A_RECV0);
        msg->msg1 = (u32)read64(asc->base + ASC_MBOX_I2A_RECV1);
    }
    dma_rmb();

    // printf("received msg: %lx %x\n", msg->msg0, msg->msg1);

    return true;
}

bool asc_recv_timeout(asc_dev_t *asc, struct asc_message *msg, u32 delay_usec)
{
    u64 timeout = timeout_calculate(delay_usec);
    while (!timeout_expired(timeout)) {
        if (asc_recv(asc, msg))
            return true;
    }
    return false;
}

bool asc_can_send(asc_dev_t *asc)
{
    if (asc->messagebox)
        return read32(asc->base + ASC_MSGBOX_STATUS) & ASC_MSGBOX_TX;
    return !(read32(asc->base + ASC_MBOX_A2I_CONTROL) & ASC_MBOX_CONTROL_FULL);
}

bool asc_send(asc_dev_t *asc, const struct asc_message *msg)
{
    u64 timeout = timeout_calculate(200000);
    while (!asc_can_send(asc)) {
        if (timeout_expired(timeout)) {
            printf("asc: A2I mailbox full for 200ms. Is the ASC stuck?");
            return false;
        }
    }

    dma_wmb();
    if (asc->messagebox) {
        u64 base = asc->base + ASC_MSGBOX_SEND;
        write32(base, msg->msg0);
        write32(base + 4, msg->msg0 >> 32);
        write32(base + 8, msg->msg1);
        write32(base + 12, 0);
    } else {
        write64(asc->base + ASC_MBOX_A2I_SEND0, msg->msg0);
        write64(asc->base + ASC_MBOX_A2I_SEND1, msg->msg1);
    }

    // printf("sent msg: %lx %x\n", msg->msg0, msg->msg1);
    return true;
}
