// SPDX-License-Identifier: GPL-2.0
/* Exact-build experimental connected PMP reprobe. No retained driver pointers,
 * no private callbacks, no controller reset. Default: read-only snapshot. */
#ifdef DX213_HOST_TEST
#include "tests/mock_kernel.h"
#else
#include <linux/module.h>
#include <linux/init.h>
#include <linux/pci.h>
#include <linux/libata.h>
#include <linux/kallsyms.h>
#include <linux/utsname.h>
#include <linux/mutex.h>
#include <linux/string.h>
#include <linux/synobios.h>
#include <linux/workqueue.h>
#include <scsi/scsi_device.h>
#include <scsi/scsi_host.h>
#endif
#include "firmware_guard.h"
#define DX213_MV_FLAG 8U
#define TAG "dx213_boot: "
#define BUSY_FLAGS (ATA_PFLAG_EH_PENDING | ATA_PFLAG_EH_IN_PROGRESS | \
 ATA_PFLAG_INITIALIZING | ATA_PFLAG_UNLOADING | ATA_PFLAG_UNLOADED | \
 ATA_PFLAG_SUSPENDED | ATA_PFLAG_PM_PENDING | ATA_PFLAG_RESETTING | \
 ATA_PFLAG_PMP_PMCTL | ATA_PFLAG_SYNO_DS_WAKING)
static int action;
static bool isolated_test;
/* Immutable snapshots exposed through sysfs; never live pointer dereferences. */
static int state = 6;
static unsigned int flags_snapshot, sstatus_snapshot, pmp_unique, device_class;
static unsigned int disk_mask;
/* Diagnostic snapshots only: do not relax any eligibility guard. */
static unsigned int raw_ports, pmp_links_snapshot, pmp_vendor, pmp_device, pmp_emid;
static unsigned int refusal_detail; /* 1=identity 2=link-count 3=link-pointer 4=child */
module_param(raw_ports, uint, 0400);
module_param(pmp_links_snapshot, uint, 0400);
module_param(pmp_vendor, uint, 0400);
module_param(pmp_device, uint, 0400);
module_param(pmp_emid, uint, 0400);
module_param(refusal_detail, uint, 0400);
module_param(action, int, 0400);
module_param(isolated_test, bool, 0400);
module_param(state, int, 0400);
module_param(flags_snapshot, uint, 0400);
module_param(sstatus_snapshot, uint, 0400);
module_param(pmp_unique, uint, 0400);
module_param(device_class, uint, 0400);
module_param(disk_mask, uint, 0400);
MODULE_PARM_DESC(action, "0=snapshot; 1=clear flag and queue targeted reprobe");
MODULE_PARM_DESC(state, "1=absent 2=eligible 3=queued 4=ready 5=busy 6=refused");

static int firmware_guard(void)
{
    unsigned long address;
    const struct new_utsname *u = init_utsname();

    BUILD_BUG_ON(SYNO_STATUS_IS_MV9235 != DX213_MV_FLAG);
    BUILD_BUG_ON(offsetof(struct ata_host, dev) != 0x08);
    BUILD_BUG_ON(offsetof(struct ata_host, n_ports) != 0x18);
    BUILD_BUG_ON(offsetof(struct ata_host, eh_mutex) != 0x38);
    BUILD_BUG_ON(offsetof(struct ata_host, ports) != 0x78);
    BUILD_BUG_ON(offsetof(struct ata_port, port_no) != 0x128);
    BUILD_BUG_ON(offsetof(struct ata_port, link) != 0x2280);
    /* Independently observed in the official 90080 kernel disassembly. */
    BUILD_BUG_ON(offsetof(struct ata_port, link) +
                 offsetof(struct ata_link, uiStsFlags) != 0x5108);
    BUILD_BUG_ON(offsetof(struct ata_port, link) +
                 offsetof(struct ata_link, device) +
                 offsetof(struct ata_device, gscr) != 0x4500);

    if (strcmp(u->release, "4.4.302+") ||
        strcmp(u->version, "#90080 SMP Wed Jul 22 00:08:29 CST 2026") ||
        strcmp(u->machine, "x86_64") ||
        !syno_is_hw_version("DS920+")) {
        pr_err(TAG "REFUSED: model/kernel is not the exact tested build target\n");
        return -EINVAL;
    }
    address = kallsyms_lookup_name("syno_pmp_ports_num.part.0");
    /* Deliberately fixed-address and fixed-byte: relocation also fails closed. */
    if (address != DX213_HELPER_ADDRESS ||
        memcmp((const void *)address, dx213_helper_bytes,
               sizeof(dx213_helper_bytes))) {
        pr_err(TAG "REFUSED: rejection helper address/bytes differ\n");
        return -EINVAL;
    }
    pr_info(TAG "Exact model, kernel and rejection-helper fingerprint matched\n");
    return 0;
}


static bool dx213_identity(struct ata_port *ap)
{
    /* syno_pmp_ports_num() normalizes this Synology 3xxx PMP to five
     * links even when GSCR reports six. Confirmed on the target DX213.
     * Keep raw identity separate from the attached-link count guard. */
    unsigned int ports = sata_pmp_gscr_ports(ap->link.device[0].gscr);
    return IS_SYNOLOGY_DX213(ap->PMSynoUnique) && ap->PMSynoEMID == 0 &&
        sata_pmp_gscr_vendor(ap->link.device[0].gscr) == 0x1095 &&
        sata_pmp_gscr_devid(ap->link.device[0].gscr) == 0x3726 &&
        (ports == 5 || ports == 6);
}

static bool virtual_or_none(struct ata_device *d)
{
    struct scsi_device *s = d->sdev;
    return !s || (s->type == TYPE_PROCESSOR && s->channel == 15 &&
                  s->id == 0 && s->lun == 0);
}

static int __init dx213_init(void)
{
    struct pci_dev *pdev;
    struct ata_host *host;
    struct ata_port *ap;
    struct ata_device *dev;
    unsigned long irqflags;
    unsigned int i, j, before;
    u32 sstatus;
    int rc;

    if (action < 0 || action > 1 || (action && !isolated_test))
        return -EINVAL;
    rc = firmware_guard();
    if (rc) return rc;
    pdev = pci_get_domain_bus_and_slot(0, 1, PCI_DEVFN(0, 0));
    if (!pdev) return -ENODEV;
    rc = -ENODEV;
    if (pdev->vendor != 0x1b4b || pdev->device != 0x9235) goto put;
    rc = -EBUSY;
    if (!device_trylock(&pdev->dev)) goto put;
    rc = -ENODEV;
    if (!pdev->dev.driver || strcmp(pdev->dev.driver->name,"ahci")) goto unlock_device;
    rc = -EBUSY;
    if (pdev->current_state != PCI_D0) goto unlock_device;
    host = pci_get_drvdata(pdev);
    rc = -EINVAL;
    if (!host || host->dev != &pdev->dev || host->n_ports != 4) goto unlock_device;
    ap = host->ports[3];
    if (!ap || ap->host != host || ap->port_no != 3 || ap->print_id != 6 ||
        ap->link.ap != ap || ap->lock != &host->lock ||
        !(ap->flags & ATA_FLAG_SATA) || !(ap->flags & ATA_FLAG_PMP) ||
        !ap->scsi_host || !ap->ops || !ap->ops->error_handler || !ap->ops->sched_eh)
        goto unlock_device;
    /* Non-blocking acquisition, same scan->host lock direction as hotplug.
     * Never wait for EH under any of these locks. */
    rc = -EBUSY;
    if (!mutex_trylock(&ap->scsi_scan_mutex)) goto unlock_device;
    if (!mutex_trylock(&host->eh_mutex)) goto unlock_scan;
    spin_lock_irqsave(ap->lock, irqflags);
    for (i=0; i<host->n_ports; i++)
        if (!host->ports[i] || (host->ports[i]->pflags & BUSY_FLAGS)) goto unlock_spin;
    if (host->eh_owner || scsi_host_in_recovery(ap->scsi_host) ||
        work_busy(&ap->hotplug_task.work) || work_busy(&ap->scsi_rescan_task))
        goto unlock_spin;
    before = ap->link.uiStsFlags;
    rc = sata_scr_read(&ap->link, SCR_STATUS, &sstatus);
    if (rc) goto unlock_spin;
    flags_snapshot = before;
    sstatus_snapshot = sstatus;
    pmp_unique = ap->PMSynoUnique;
    device_class = ap->link.device[0].class;
    raw_ports = sata_pmp_gscr_ports(ap->link.device[0].gscr);
    pmp_links_snapshot = ap->nr_pmp_links;
    pmp_vendor = sata_pmp_gscr_vendor(ap->link.device[0].gscr);
    pmp_device = sata_pmp_gscr_devid(ap->link.device[0].gscr);
    pmp_emid = ap->PMSynoEMID;
    rc = -EBUSY;
    if ((before & SYNO_STATUS_GPIO_CTRL) || ap->qc_active || ap->nr_active_links)
        goto unlock_spin;
    rc = -EINVAL;
    /* Already working: snapshot only, no reprobe, never rewrite its flag. */
    if (ap->nr_pmp_links) {
        if ((before & DX213_MV_FLAG) || !dx213_identity(ap)) {
            refusal_detail = 1; goto unlock_spin;
        }
        if (ap->nr_pmp_links != 5) { refusal_detail = 2; goto unlock_spin; }
        if (!ap->pmp_link) { refusal_detail = 3; goto unlock_spin; }
        for (i=0; i<5; i++) for (j=0; j<ATA_MAX_DEVICES; j++) {
            dev = &ap->pmp_link[i].device[j];
            if (!ata_dev_enabled(dev)) continue;
            if (i>1 || j || dev->class != ATA_DEV_ATA || !dev->sdev ||
                dev->sdev->sdev_state != SDEV_RUNNING) {
                refusal_detail = 4;
                pr_info(TAG "refused child link=%u dev=%u class=%u sdev_present=%u sdev_state=%d\n",
                        i, j, dev->class, !!dev->sdev,
                        dev->sdev ? (int)dev->sdev->sdev_state : -1);
                goto unlock_spin;
            }
            disk_mask |= 1U << i;
        }
        state = disk_mask ? 4 : 5;
        rc = action ? -EALREADY : 0;
        goto unlock_spin;
    }
    /* Refuse stale allocated PMP links, even if nr_pmp_links is zero. */
    if (ap->pmp_link) goto unlock_spin;
    for (i=0; i<ATA_MAX_DEVICES; i++) {
        dev = &ap->link.device[i];
        if (ata_dev_enabled(dev) || !virtual_or_none(dev)) goto unlock_spin;
    }
    if ((sstatus & 0xf) == 0) {
        state = 1; rc = 0; goto unlock_spin; /* absent: do not change flag */
    }
    if ((sstatus & 0xf) != 3 || !dx213_identity(ap) ||
        !(before & DX213_MV_FLAG)) goto unlock_spin;
    /* Same probe request as ata_scsi_user_scan() in exact Synology source.
     * Require no stale request so we do not clobber another operation. */
    if (ap->link.eh_info.action || ap->link.eh_info.probe_mask) {
        rc = -EBUSY; goto unlock_spin;
    }
    state = 2; rc = 0;
    if (!action) goto unlock_spin;
    WRITE_ONCE(ap->link.uiStsFlags, before & ~DX213_MV_FLAG);
    ap->link.eh_info.probe_mask |= ATA_ALL_DEVICES;
    ap->link.eh_info.action |= ATA_EH_RESET;
    ata_port_schedule_eh(ap);
    state = 3;
    pr_info(TAG "QUEUED: ata6 flags 0x%x -> 0x%x; targeted driver reprobe, not completion\n",
            before, before & ~DX213_MV_FLAG);
unlock_spin:
    spin_unlock_irqrestore(ap->lock, irqflags);
    mutex_unlock(&host->eh_mutex);
unlock_scan:
    mutex_unlock(&ap->scsi_scan_mutex);
unlock_device:
    device_unlock(&pdev->dev);
put:
    pci_dev_put(pdev);
    if (rc == -EBUSY) state = 5;
    pr_info(TAG "snapshot state=%d flags=0x%x sstatus=0x%x unique=0x%x class=%u disk_mask=0x%x rc=%d\n",
            state, flags_snapshot, sstatus_snapshot, pmp_unique, device_class, disk_mask, rc);
    pr_info(TAG "diagnostic raw_ports=%u pmp_links=%u vendor=0x%x device=0x%x emid=%u refusal_detail=%u\n",
            raw_ports, pmp_links_snapshot, pmp_vendor, pmp_device, pmp_emid, refusal_detail);
    /* Read-only busy/refused snapshots remain readable through module params. */
    if (!action && (rc == -EBUSY || rc == -EINVAL)) return 0;
    return rc;
}
static void __exit dx213_exit(void)
{
    pr_info(TAG "unloaded; no rollback; queued work belongs to libata, no module callbacks\n");
}
module_init(dx213_init);
module_exit(dx213_exit);
MODULE_LICENSE("GPL");
MODULE_VERSION("0.2.2-experimental");
MODULE_DESCRIPTION("Exact-build DS920+ DX213 connected pre-storage reprobe experiment");
