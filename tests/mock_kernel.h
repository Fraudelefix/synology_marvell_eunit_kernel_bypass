/* Test-only stand-ins. These do not simulate real hardware or prove kernel ABI.
 * The real kernel build separately enforces all BUILD_BUG_ON layout guards. */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <errno.h>
#include <assert.h>
#include <stdio.h>
typedef uint32_t u32;
#define __init
#define __exit
#define module_param(...)
#define MODULE_PARM_DESC(...)
#define MODULE_LICENSE(...)
#define MODULE_DESCRIPTION(...)
#define MODULE_VERSION(...)
#define module_init(...)
#define module_exit(...)
#define BUILD_BUG_ON(x) ((void)0)
#define PCI_DEVFN(a,b) (((a)<<3)|(b))
#define PCI_D0 0
#define SCR_STATUS 0
#define ATA_MAX_DEVICES 2
#define ATA_FLAG_SATA (1U<<1)
#define ATA_FLAG_PMP (1U<<19)
#define SYNO_STATUS_IS_MV9235 8U
#define SYNO_STATUS_GPIO_CTRL 4U
#define ATA_PFLAG_EH_PENDING (1U<<0)
#define ATA_PFLAG_EH_IN_PROGRESS (1U<<1)
#define ATA_PFLAG_RESETTING (1U<<8)
#define ATA_PFLAG_INITIALIZING (1U<<7)
#define ATA_PFLAG_UNLOADING (1U<<9)
#define ATA_PFLAG_UNLOADED (1U<<10)
#define ATA_PFLAG_SUSPENDED (1U<<17)
#define ATA_PFLAG_PM_PENDING (1U<<18)
#define ATA_PFLAG_PMP_PMCTL (1U<<25)
#define ATA_PFLAG_SYNO_DS_WAKING (1U<<29)

struct mutex { int held; };
struct device_driver { const char *name; };
struct device { struct mutex lock; struct device_driver *driver; };
#define ATA_DEV_ATA 1
#define ATA_DEV_PMP_UNSUP 6
#define TYPE_PROCESSOR 3
#define SDEV_RUNNING 2
#define ATA_ALL_DEVICES 3
#define ATA_EH_RESET 12
#define IS_SYNOLOGY_DX213(x) (((x)>>2)==0x16)
struct scsi_device { int type, channel, id, lun, sdev_state; };
struct Scsi_Host { int recovery; };
struct work_struct { int busy; };
struct delayed_work { struct work_struct work; };
struct ata_port_operations { void (*error_handler)(void); void (*sched_eh)(void); };
struct ata_device { bool enabled; unsigned int class; struct scsi_device *sdev; unsigned int gscr[3]; };
struct ata_port;
struct ata_link { struct ata_port *ap; unsigned int uiStsFlags;
                  struct ata_device device[2]; struct { unsigned int probe_mask, action; } eh_info; };
struct ata_host { struct device *dev; unsigned int n_ports; int lock;
                  struct mutex eh_mutex; void *eh_owner; struct ata_port *ports[4]; };
struct ata_port { struct ata_host *host; unsigned int port_no, print_id;
                  struct ata_link link; int *lock; unsigned long flags;
                  unsigned int pflags, qc_active; int nr_pmp_links,nr_active_links;
 struct ata_link *pmp_link; struct mutex scsi_scan_mutex;
 struct delayed_work hotplug_task; struct work_struct scsi_rescan_task;
 struct Scsi_Host *scsi_host; struct ata_port_operations *ops;
 unsigned int PMSynoUnique, PMSynoEMID; };
struct pci_dev { unsigned int vendor,device,current_state;
                 struct device dev; struct ata_host *data; };
struct new_utsname { char release[65],version[65],machine[65]; };

static struct pci_dev test_pci;
static struct ata_host test_host;
static struct ata_port test_ports[4];
static struct device_driver test_driver;
static struct new_utsname test_uts;
static bool test_model_ok, test_symbol_ok, test_bytes_ok, test_pci_present;
static int test_reads,test_writes,test_refs,test_scr_error;
static u32 test_sstatus;

static const struct new_utsname *init_utsname(void) { return &test_uts; }
static bool syno_is_hw_version(const char *s) {
    assert(!strcmp(s,"DS920+")); return test_model_ok;
}
static unsigned long kallsyms_lookup_name(const char *s) {
    assert(!strcmp(s,"syno_pmp_ports_num.part.0"));
    return test_symbol_ok ? 0xffffffff8141f0f0UL : 0;
}
static int test_memcmp(const void *a,const void *b,size_t n) {
    assert((uintptr_t)a == 0xffffffff8141f0f0UL && b && n==193);
    return test_bytes_ok ? 0 : 1;
}
#define memcmp test_memcmp
static struct pci_dev *pci_get_domain_bus_and_slot(int d,int b,int f) {
    assert(d==0 && b==1 && f==0);
    if (!test_pci_present) return NULL;
    ++test_refs; return &test_pci;
}
static void pci_dev_put(struct pci_dev *p) { assert(p==&test_pci); --test_refs; }
static int mutex_trylock(struct mutex *m) {
    if (m->held) return 0;
    m->held=1; return 1;
}
static void mutex_unlock(struct mutex *m) { assert(m->held); m->held=0; }
static int device_trylock(struct device *d) { return mutex_trylock(&d->lock); }
static void device_unlock(struct device *d) { mutex_unlock(&d->lock); }
static struct ata_host *pci_get_drvdata(struct pci_dev *p) { return p->data; }
#define spin_lock_irqsave(lock,flags) do { assert(!*(lock)); *(lock)=1; flags=0; } while(0)
#define spin_unlock_irqrestore(lock,flags) do { assert(*(lock)); *(lock)=0; (void)flags; } while(0)
static int sata_scr_read(struct ata_link *l,int reg,u32 *val) {
    assert(l==&test_ports[3].link && reg==SCR_STATUS);
    assert(test_pci.dev.lock.held && test_host.eh_mutex.held && test_host.lock);
    ++test_reads; *val=test_sstatus; return test_scr_error;
}
static bool ata_dev_enabled(struct ata_device *d) { return d->enabled; }
#define WRITE_ONCE(dst,val) do { \
    assert(&(dst)==&test_ports[3].link.uiStsFlags); \
    assert(test_pci.dev.lock.held && test_host.eh_mutex.held && test_host.lock); \
    ++test_writes; (dst)=(val); \
} while(0)
#define pr_info(...) ((void)0)
#define pr_err(...) ((void)0)

static int test_schedules;
static struct Scsi_Host test_shost;
static struct ata_port_operations test_ops;
static struct ata_link test_links[5];
static struct scsi_device test_disk, test_virtual;
static void fake_op(void) {}
static int work_busy(struct work_struct *w) {return w->busy;}
static int scsi_host_in_recovery(struct Scsi_Host *s) {return s->recovery;}
static unsigned int sata_pmp_gscr_vendor(unsigned int *g) {return g[0];}
static unsigned int sata_pmp_gscr_devid(unsigned int *g) {return g[1];}
static unsigned int sata_pmp_gscr_ports(unsigned int *g) {return g[2];}
static void ata_port_schedule_eh(struct ata_port *ap) {
 assert(ap==&test_ports[3] && test_host.lock && test_host.eh_mutex.held);
 assert(ap->scsi_scan_mutex.held && test_pci.dev.lock.held);
 assert(!(ap->link.uiStsFlags&8));
 assert(ap->link.eh_info.probe_mask==ATA_ALL_DEVICES);
 assert(ap->link.eh_info.action==ATA_EH_RESET);
 test_schedules++;
}
